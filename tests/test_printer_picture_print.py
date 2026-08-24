import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QSettings, QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from printer_picture_print import (
    PictureItem, export_picture_pdf, layout_capacity, page_size_mm, paginate,
    paper_api_key, preview_page,
)
from printer_picture_page import PictureQueueWorker, PrintPicturesPage
import printer_agent_gui


class PrinterPicturePrintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_page_sizes_and_layout_capacities(self):
        self.assertEqual(page_size_mm("A4", "Portrait"), (210.0, 297.0))
        self.assertEqual(page_size_mm("A4", "Landscape"), (297.0, 210.0))
        self.assertEqual(layout_capacity("Four photos"), 4)
        self.assertEqual(paper_api_key("4 x 6 in"), "4X6")

    def test_pagination_includes_copies_of_each_picture(self):
        items = [PictureItem("one.jpg"), PictureItem("two.jpg"), PictureItem("three.jpg")]
        pages = paginate(items, "Four photos", copies=2)
        self.assertEqual([len(page) for page in pages], [4, 2])

    def test_preview_and_pdf_use_the_same_multi_page_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for index, color in enumerate(("#27c992", "#35a7ff", "#f3a64a")):
                path = Path(tmp) / f"picture-{index}.png"
                image = QImage(320 + index * 20, 220, QImage.Format.Format_RGB32)
                image.fill(QColor(color))
                self.assertTrue(image.save(str(path)))
                paths.append(PictureItem(str(path)))

            preview = preview_page(
                paths[:2], paper="A4", orientation="Landscape", layout="Two photos",
                margin_mm=5, fit_to_frame=True, max_size=QSize(600, 420),
            )
            self.assertFalse(preview.isNull())
            self.assertGreater(preview.width(), preview.height())

            output = Path(tmp) / "pictures.pdf"
            pages = export_picture_pdf(
                str(output), paths, paper="A4", orientation="Portrait",
                layout="Two photos", copies=1, margin_mm=5, fit_to_frame=False,
            )
            self.assertEqual(pages, 2)
            self.assertTrue(output.read_bytes().startswith(b"%PDF"))
            self.assertGreater(output.stat().st_size, 1000)

    def test_picture_page_lists_only_online_enabled_printers(self):
        page = PrintPicturesPage()
        page.set_printer_agents([
            {"agent_id": "a1", "computer_name": "Photo PC", "is_online": True, "is_enabled": True,
             "printers": [
                 {"printer_name": "Photo Printer", "status": "online", "is_default": True},
                 {"printer_name": "Offline Printer", "status": "offline"},
                 {"printer_name": "Disabled Printer", "status": "online", "is_enabled": False},
             ]},
            {"agent_id": "a2", "computer_name": "Disabled PC", "is_online": True, "is_enabled": False,
             "printers": [{"printer_name": "Hidden", "status": "online"}]},
        ])
        self.assertEqual(page.printer.count(), 1)
        self.assertEqual(page.printer.currentData()["printer_name"], "Photo Printer")
        self.assertTrue(page.queue_button.isEnabled())
        self.assertTrue(page.paper.isEnabled())
        self.assertTrue(page.orientation.isEnabled())
        self.assertTrue(page.quality.isEnabled())
        self.assertTrue(page.paper_type.isEnabled())
        self.assertTrue(page.color_mode.isEnabled())

    def test_custom_paper_and_borderless_controls_feed_composition(self):
        page = PrintPicturesPage()
        page.paper.setCurrentText("Custom Size")
        page.custom_width.setValue(100.0)
        page.custom_height.setValue(150.0)
        page.borderless.setChecked(True)
        options = page._composition_options()
        self.assertTrue(page.custom_width.isEnabled())
        self.assertFalse(page.margin.isEnabled())
        self.assertEqual(options["custom_width_mm"], 100.0)
        self.assertEqual(options["custom_height_mm"], 150.0)
        self.assertTrue(options["borderless"])

    def test_picture_presets_persist_and_restore_advanced_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = PrintPicturesPage()
            page.settings = QSettings(str(Path(tmp) / "printer-agent.ini"), QSettings.Format.IniFormat)
            page._reload_presets()
            page.layout.setCurrentText("Four photos")
            page.margin.setValue(8)
            with patch("printer_picture_page.QInputDialog.getText", return_value=("Glossy Photo", True)):
                page.save_preset()

            page.layout.setCurrentText("Full page photo")
            page.preset.setCurrentIndex(page.preset.findData("Glossy Photo"))
            self.assertEqual(page.layout.currentText(), "Four photos")
            self.assertEqual(page.margin.value(), 8)

    def test_queue_worker_composes_pdf_and_uses_upload_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "photo.png"
            image = QImage(640, 480, QImage.Format.Format_RGB32)
            image.fill(QColor("#35a7ff"))
            self.assertTrue(image.save(str(image_path)))
            calls = []

            def request(method, path, **kwargs):
                if method == "GET":
                    return [{
                        "agent_id": "agent-1", "is_online": True, "is_enabled": True,
                        "printers": [{"printer_name": "Photo Printer", "status": "online"}],
                    }]
                calls.append((method, path, kwargs["data"], kwargs["files"]["file"][1].read(4)))
                return {"job_id": "job-picture-1", "status": "pending"}

            worker = PictureQueueWorker(
                request,
                {"agent_id": "agent-1", "printer_name": "Photo Printer"},
                [PictureItem(str(image_path))],
                {
                    "paper": "5 x 7 in", "orientation": "Portrait",
                    "layout": "Full page photo", "copies": 2,
                    "margin_mm": 5.0, "fit_to_frame": True,
                    "quality": "High", "paper_type": "Glossy", "color_mode": "Color",
                },
            )
            completed, failed = [], []
            worker.succeeded.connect(completed.append)
            worker.failed.connect(failed.append)
            worker.run()

            self.assertFalse(failed)
            self.assertEqual(completed[0]["job_id"], "job-picture-1")
            method, path, data, signature = calls[0]
            self.assertEqual((method, path), ("POST", "/api/printer/jobs/upload"))
            self.assertEqual(data["paper_size"], "5X7")
            self.assertEqual(data["copies"], 1)
            self.assertEqual(data["quality"], "high")
            self.assertEqual(data["paper_type"], "glossy")
            self.assertEqual(signature, b"%PDF")

    def test_queue_worker_rechecks_offline_target_before_composition(self):
        requests = []

        def request(method, path, **kwargs):
            requests.append((method, path))
            return []

        worker = PictureQueueWorker(
            request, {"agent_id": "offline", "printer_name": "Missing"}, [],
            {
                "paper": "A4", "orientation": "Portrait", "layout": "Full page photo",
                "copies": 1, "margin_mm": 5.0, "fit_to_frame": True,
                "quality": "Normal", "paper_type": "Automatic", "color_mode": "Color",
            },
        )
        failed = []
        worker.failed.connect(failed.append)
        worker.run()
        self.assertEqual(requests, [("GET", "/api/printer/agents")])
        self.assertIn("offline", failed[0].lower())

    def test_printer_disable_auto_hides_and_filters_picture_targets(self):
        dashboard = printer_agent_gui.PrinterAgentDashboard()
        hidden = set()
        agent = {
            "agent_id": "agent-toggle", "computer_name": "Photo PC",
            "is_online": True, "is_enabled": True,
            "printers": [{"printer_name": "Photo", "status": "online", "is_enabled": True}],
        }

        def request(method, _path, **kwargs):
            if method == "PUT":
                agent["printers"][0]["is_enabled"] = kwargs["json"]["enabled"]
                return agent
            return [agent]

        def save_config(**kwargs):
            hidden.clear()
            hidden.update(kwargs.get("hidden_printers") or [])

        dashboard._request = request
        dashboard.picture_page.request = request
        dashboard._hidden_keys = lambda: set(hidden)
        with patch("printer_agent_gui.save_agent_config", side_effect=save_config):
            dashboard.refresh_printers()
            self.assertEqual(dashboard.printers_table.rowCount(), 1)
            self.assertTrue(dashboard.picture_page.queue_button.isEnabled())

            dashboard.toggle_printer()
            self.assertEqual(dashboard.printers_table.rowCount(), 0)
            self.assertTrue(hidden)
            self.assertFalse(dashboard.picture_page.queue_button.isEnabled())

            dashboard.show_hidden.setChecked(True)
            self.assertEqual(dashboard.printers_table.item(0, 5).text(), "Disabled")
            dashboard.toggle_printer()
            self.assertFalse(hidden)
            self.assertEqual(dashboard.printers_table.rowCount(), 1)
            self.assertTrue(dashboard.picture_page.queue_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
