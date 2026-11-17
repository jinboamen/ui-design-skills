/* Offline visual demonstration only: no prize selection or network requests.
 * Copy next to index.html and load with defer; see references/v1-layout.md.
 */
(() => {
  function init() {
    document.querySelectorAll('[data-role="marquee-board"]').forEach(board => {
      if (board.dataset.previewReady) return;
      const cards = [...board.querySelectorAll('[data-role="marquee-prize"]')]
        .sort((a, b) => Number(a.dataset.marqueeIndex) - Number(b.dataset.marqueeIndex));
      const toggle = board.querySelector('[data-role="marquee-toggle"]');
      if (![8, 10, 12].includes(cards.length) || !toggle ||
          cards.some((c, i) => c.dataset.marqueeIndex !== String(i))) return;
      board.dataset.previewReady = 'true';
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
      let running = !reducedMotion.matches;
      let index = 0;
      let timer = null;
      const paint = () => cards.forEach((card, i) => {
        card.dataset.active = String(i === index);
      });
      const sync = () => {
        clearInterval(timer);
        timer = null;
        toggle.setAttribute('aria-pressed', String(running));
        toggle.setAttribute('aria-label', running ? '暂停跑马灯演示' : '开始跑马灯演示');
        board.dataset.previewRunning = String(running && !document.hidden);
        if (running && !document.hidden) timer = setInterval(() => {
          index = (index + 1) % cards.length;
          paint();
        }, 180);
      };
      toggle.addEventListener('click', () => { running = !running; sync(); });
      document.addEventListener('visibilitychange', sync);
      reducedMotion.addEventListener('change', e => {
        if (e.matches) { running = false; sync(); }
      });
      window.addEventListener('pagehide', () => clearInterval(timer));
      window.addEventListener('pageshow', sync);
      paint();
      sync();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
