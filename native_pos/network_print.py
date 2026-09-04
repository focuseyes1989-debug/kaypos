"""Native PDF submission to the existing printer queue, with durable retry."""
import base64
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import requests

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QComboBox, QPushButton, QLabel, QHBoxLayout, QMessageBox
from native_pos.config import load_config, save_config
from native_pos.protected_journal import ProtectedJournal, protect
from native_pos.tasks import TaskRunner


class PrintRejected(ValueError):
    pass


def server_url(value):
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.strip('/'):
        raise ValueError('Enter the printer server origin, for example https://192.168.110.112:8000')
    try: parsed.port
    except ValueError as exc: raise ValueError('Invalid printer server port') from exc
    return str(value).strip().rstrip('/')


def request(values, method, route, **kwargs):
    url = server_url(values['server'])
    try:
        response = requests.request(method, url + route, headers={'X-Printer-API-Key': values['api_key']},
                                    verify=values['verify_tls'], timeout=(5, 30), allow_redirects=False, **kwargs)
        if not 200 <= response.status_code < 300:
            error = PrintRejected if response.status_code in (400, 401, 403, 404, 413, 422) else ValueError
            raise error(f'Printer server returned HTTP {response.status_code}. Check connection, API key and printer permissions.')
        return response.json()
    except (requests.RequestException, requests.exceptions.JSONDecodeError) as exc:
        raise ValueError('Printer server response was not confirmed. Check the connection and recover the same request before printing again.') from exc


def online_printers(values):
    data = request(values, 'GET', '/api/printer/agents')
    return [(a['agent_id'], p['printer_name']) for a in data.get('data', []) if a.get('is_online')
            for p in a.get('printers', []) if p.get('status') == 'online']


def submit_pdf(pending):
    values = pending['payload']['values']; key = pending['payload']['request_id']
    data = base64.b64decode(values['content'], validate=True)
    try:
        result = request(values, 'POST', '/api/printer/jobs/upload',
                         data=dict(target_agent_id=values['agent'], printer_name=values['printer'], request_key=key,
                                   copies=1, paper_size=values['paper'].upper(), quality=values['quality'], source_agent_id='kay-pos-native'),
                         files={'file': ('native-receipt.pdf', data, 'application/pdf')})
    except PrintRejected as exc: return dict(rejected=str(exc))
    job = result.get('data') or {}
    if not job.get('job_id') or job.get('request_key') != key:
        raise ValueError('Incomplete printer queue response. Recover the same request.')
    return dict(job_id=job['job_id'], status=job.get('status', 'queued'), message='Printer queue confirmed')


class NetworkPrinterDialog(QDialog):
    def __init__(self, host, parent=None, pdf=None):
        super().__init__(parent); self.host = host; self.pdf = pdf; self.pending = None; self.error = ''
        self.setWindowTitle('Network receipt printer'); self.resize(660, 510)
        self.runner = TaskRunner(self); self.config = load_config(host.settings_path)
        directory = Path(host.settings_path).parent if host.settings_path else None
        self.journal = ProtectedJournal(host.store.client.server_url + '/native/network-print', host.session.user_id, directory)
        try:
            prior = self.journal.read()
            if prior and not prior.get('result'): self.pending = prior
        except (OSError, ValueError) as exc: self.error = str(exc)
        key_error = ''
        try:
            key = base64.b64decode(self.config['print_key_protected']) if self.config['print_key_protected'] else b''
            api_key = protect(key, decrypt=True).decode() if key else ''
        except (OSError, ValueError, TypeError): key_error = 'Saved API key cannot be unlocked. Enter and save a replacement key.'; api_key = ''
        body = QVBoxLayout(self); form = QFormLayout(); body.addLayout(form)
        self.server = QLineEdit(self.config['print_server_url'] or self.config['server_url']); form.addRow('Printer server URL', self.server)
        self.key = QLineEdit(api_key); self.key.setEchoMode(QLineEdit.EchoMode.Password); form.addRow('Printer client API key', self.key)
        self.verify = QCheckBox('Verify HTTPS certificate'); self.verify.setChecked(bool(self.config['print_verify_tls'])); form.addRow(self.verify)
        self.agent = QLineEdit(self.config['print_agent']); form.addRow('Agent ID', self.agent)
        self.printer = QLineEdit(self.config['print_remote_name']); form.addRow('Printer name', self.printer)
        self.choices = QComboBox(); self.choices.activated.connect(self.select); form.addRow('Online printers', self.choices)
        self.refresh_button = QPushButton('Find online printers'); self.refresh_button.clicked.connect(self.refresh); form.addRow(self.refresh_button)
        self.message = QLabel('Network printing sends one PDF copy, including receipt images. Printer Agent must support PDF printing. Queue confirmation does not confirm paper output.')
        self.message.setWordWrap(True); self.message.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.message, 1)
        row = QHBoxLayout(); body.addLayout(row)
        self.save_button = QPushButton('Save connection'); self.save_button.clicked.connect(self.save)
        self.send_button = QPushButton('Queue PDF…'); self.send_button.clicked.connect(self.send)
        self.recover_button = QPushButton('Recover pending print'); self.recover_button.clicked.connect(self.recover)
        close = QPushButton('Close'); close.clicked.connect(self.reject)
        for button in (self.save_button, self.send_button, self.recover_button, close): row.addWidget(button)
        if self.pending:
            v = self.pending['payload']['values']; self.server.setText(v['server']); self.agent.setText(v['agent']); self.printer.setText(v['printer']); self.verify.setChecked(v['verify_tls']); self.key.setText(v['api_key'])
            self.message.setText('A print request is unresolved. Recover it before submitting another copy. You can replace an expired API key here.')
        if self.error: self.message.setText('Recovery/configuration needs attention: ' + self.error)
        elif key_error and not self.pending: self.message.setText(key_error)
        self.runner.idle.connect(self.update_enabled); self.update_enabled()

    def update_enabled(self):
        busy = self.runner.busy
        edit = self.host.session.can('edit_settings')
        for widget in (self.server, self.verify, self.agent, self.printer, self.choices): widget.setEnabled(not busy and edit and not self.pending)
        self.key.setEnabled(not busy and edit)
        self.refresh_button.setEnabled(not busy and edit and not self.pending)
        self.save_button.setEnabled(not busy and edit and not self.pending and not self.error)
        self.send_button.setEnabled(not busy and bool(self.pdf) and not self.pending and not self.error and self.host.session.can('print_receipt'))
        self.recover_button.setEnabled(not busy and bool(self.pending) and not self.error and self.host.session.can('print_receipt'))

    def values(self):
        return dict(server=server_url(self.server.text()), api_key=self.key.text().strip(), verify_tls=self.verify.isChecked(), agent=self.agent.text().strip(), printer=self.printer.text().strip())

    def select(self, index):
        pair = self.choices.itemData(index)
        if pair: self.agent.setText(pair[0]); self.printer.setText(pair[1])

    def run(self, operation, success):
        self.runner.start(operation, success, self.message.setText); self.update_enabled()

    def refresh(self):
        try: values = self.values()
        except ValueError as exc: self.message.setText(str(exc)); return
        def done(rows):
            self.choices.clear()
            for agent, printer in rows: self.choices.addItem(printer + ' · ' + agent, (agent, printer))
            self.message.setText(f'{len(rows)} online printer(s). Select one to use its agent and printer name.')
            if rows: self.select(0)
        self.run(lambda: online_printers(values), done)

    def save(self):
        if not self.host.session.can('edit_settings'): return
        try:
            v = self.values(); encrypted = base64.b64encode(protect(v['api_key'].encode())).decode() if v['api_key'] else ''
            saved = save_config(dict(print_server_url=v['server'], print_agent=v['agent'], print_remote_name=v['printer'], print_verify_tls=v['verify_tls'], print_key_protected=encrypted), self.host.settings_path)
            self.host.config.update(saved); self.message.setText('Connection saved for this Windows account. No job was sent.')
        except (OSError, ValueError) as exc: self.message.setText(str(exc))

    def send(self):
        if self.pending or not self.pdf or not self.host.session.can('print_receipt'): return
        try:
            v = self.values()
            if not v['agent'] or not v['printer']: raise ValueError('Select an Agent ID and printer first')
            if len(self.pdf) > 20 * 1024 * 1024: raise ValueError('Receipt PDF exceeds 20 MB')
            if QMessageBox.question(self, 'Queue network receipt', f"Send one PDF copy to {v['printer']} on agent {v['agent']}?") != QMessageBox.StandardButton.Yes: return
            v.update(content=base64.b64encode(self.pdf).decode(), paper=self.config['receipt_paper'], quality='high' if self.config['receipt_dpi'] == 600 else 'normal')
            pending = dict(payload=dict(request_id=str(uuid4()), values=v))
            self.journal.write(pending); self.pending = pending; self.recover()
        except (OSError, ValueError) as exc: self.message.setText(str(exc)); self.update_enabled()

    def recover(self):
        if not self.pending or self.runner.busy or not self.host.session.can('print_receipt'): return
        prior_attempt = bool(self.pending.get('attempted'))
        self.pending['payload']['values']['api_key'] = self.key.text().strip()
        self.pending['attempted'] = True
        try: self.journal.write(self.pending)
        except OSError as exc: self.message.setText(str(exc)); return
        def done(result):
            if result.get('rejected'):
                if prior_attempt:
                    self.message.setText('Recovery was rejected; the earlier request may still be queued. Restore access and recover again. ' + result['rejected']); return
                try: self.journal.clear()
                except OSError as exc: self.message.setText('Rejected, but recovery file could not be cleared: ' + str(exc)); return
                self.pending = None; self.message.setText('Print was not queued. ' + result['rejected']); return
            try: self.journal.write(dict(self.pending, result=result))
            except OSError as exc: self.message.setText('Queue responded, but recovery record could not be saved: ' + str(exc)); return
            self.pending = None; self.pdf = None
            self.message.setText(f"Queue confirmed · {result['job_id']} · {result['status']}. Check Printer Server for physical output or failed jobs.")
        def submit():
            authorization = self.host.store.client._request('GET', '/api/native/printing/authorize')
            if not authorization.get('allowed'): raise ValueError('POS server did not authorize receipt printing')
            return submit_pdf(self.pending)
        self.run(submit, done)

    def reject(self):
        if not self.runner.busy: super().reject()

    def closeEvent(self, event):
        if self.runner.busy: event.ignore()
        else: super().closeEvent(event)
