(() => {
  'use strict';
  const connection = document.querySelector('#connection');
  const clock = document.querySelector('#clock');
  const fullscreen = document.querySelector('#fullscreen');
  const install = document.querySelector('#install');
  let installPrompt = null;

  function setConnection(ok) {
    connection.className = `connection ${ok ? 'online' : 'offline'}`;
    connection.querySelector('span').textContent = ok ? 'Server connected' : 'Server unavailable';
  }
  async function checkServer() {
    try {
      const response = await fetch('/health', {cache: 'no-store'});
      const value = await response.json();
      setConnection(response.ok && value.ok === true);
    } catch (_) { setConnection(false); }
  }
  function updateClock() {
    clock.textContent = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(new Date());
  }
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) { /* Browser or device declined fullscreen. */ }
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement ? 'Exit Full Screen' : 'Full Screen';
  });
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); installPrompt = event; install.hidden = false;
  });
  install.addEventListener('click', async () => {
    if (!installPrompt) return;
    installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; install.hidden = true;
  });
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/touch-pos/service-worker.js', {scope: '/touch-pos/'}).catch(() => {});
  }
  updateClock(); checkServer();
  setInterval(updateClock, 30000); setInterval(checkServer, 30000);
})();
