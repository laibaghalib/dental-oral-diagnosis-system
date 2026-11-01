/* ============================================================
   DentalAI — Main JavaScript
   Place this file in: final/static/main.js
   Then link at bottom of index.html (after swiper script):
     <script src="{{ url_for('static', filename='main.js') }}"></script>
   ============================================================ */

/* ── SWIPER ── */
new Swiper('.homeSlider', {
  loop: true,
  speed: 800,
  autoplay: { delay: 4000, disableOnInteraction: false },
  pagination: { el: '.swiper-pagination', clickable: true },
  navigation: { nextEl: '.swiper-button-next', prevEl: '.swiper-button-prev' },
});

/* ── NAVBAR SCROLL ── */
window.addEventListener('scroll', () => {
  const nav = document.getElementById('mainNav');
  if (window.scrollY > 50) {
    nav.style.background = 'rgba(10,22,40,1)';
    nav.style.boxShadow  = '0 4px 24px rgba(0,0,0,0.3)';
  } else {
    nav.style.background = 'rgba(10,22,40,0.92)';
    nav.style.boxShadow  = 'none';
  }
});

/* ── SCROLL REVEAL ── */
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll('.card, .list-item, .stat-card').forEach(el => {
  el.classList.add('reveal');
  revealObserver.observe(el);
});

/* ── SIDE DRAWER (mobile) ── */
function toggleDrawer() {
  const drawer  = document.getElementById('sideDrawer');
  const overlay = document.getElementById('navOverlay');
  const content = document.getElementById('pageContent');
  const nav     = document.getElementById('mainNav');
  const isOpen  = drawer.style.transform === 'translateX(0px)';

  drawer.style.transform   = isOpen ? 'translateX(-260px)' : 'translateX(0px)';
  overlay.style.display    = isOpen ? 'none' : 'block';
  content.style.marginLeft = isOpen ? '0' : '260px';
  nav.style.marginLeft     = isOpen ? '0' : '260px';
}

/* ── PROFILE DROPDOWN ── */
function toggleProfile() {
  const dd = document.getElementById('profileDropdown');
  if (dd) dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
  const dd = document.getElementById('profileDropdown');
  if (dd && !e.target.closest('[onclick="toggleProfile()"]') && !dd.contains(e.target)) {
    dd.style.display = 'none';
  }
});

/* ── LOGOUT ── */
function logoutUser() {
  window.location.href = '/auth/logout';
}

/* ── TOAST ── */
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

/* ── FAQ ACCORDION ── */
function toggleFaq(btn) {
  const answer = btn.nextElementSibling;
  const icon   = btn.querySelector('.faq-icon');
  const isOpen = answer.style.display === 'block';

  // Close all open FAQs first
  document.querySelectorAll('.faq-answer').forEach(a => a.style.display = 'none');
  document.querySelectorAll('.faq-icon').forEach(i => {
    i.style.transform = 'rotate(0deg)';
    i.innerHTML = '<i class="fa-solid fa-plus"></i>';
  });

  // Open the clicked one if it was closed
  if (!isOpen) {
    answer.style.display = 'block';
    icon.style.transform = 'rotate(45deg)';
    icon.innerHTML = '<i class="fa-solid fa-xmark"></i>';
  }
}

/* ── ANNE CHAT ── */
let anneChatHistory = [];

function openAnneChat() {
  document.getElementById('anneOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.getElementById('anneTime').textContent =
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function closeAnneChat() {
  document.getElementById('anneOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

// Close Anne overlay when clicking outside the phone shell
document.getElementById('anneOverlay').addEventListener('click', function(e) {
  if (e.target === this) closeAnneChat();
});

async function sendAnneMsg() {
  const input = document.getElementById('anneInput');
  const text  = input.value.trim();
  if (!text) return;
  input.value = '';

  const area = document.getElementById('anneMessages');
  const now  = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // Append user message
  const userWrap = document.createElement('div');
  userWrap.className = 'anne-msg-wrap-user';
  userWrap.innerHTML = `
    <div class="anne-msg-bubble anne-msg-user">${text}</div>
    <div class="anne-msg-time">${now}</div>
  `;
  area.appendChild(userWrap);
  area.scrollTop = area.scrollHeight;

  // Show typing indicator
  const typingWrap = document.createElement('div');
  typingWrap.className = 'anne-msg-wrap-ai';
  typingWrap.innerHTML = `
    <div class="anne-typing">
      <div class="anne-typing-dot"></div>
      <div class="anne-typing-dot"></div>
      <div class="anne-typing-dot"></div>
    </div>
  `;
  area.appendChild(typingWrap);
  area.scrollTop = area.scrollHeight;

  anneChatHistory.push({ role: 'user', content: text });

  try {
    const res  = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: anneChatHistory }),
      credentials: 'include'
    });
    const data = await res.json();
    typingWrap.remove();

    const reply = data.success ? data.reply : 'Sorry, I could not connect. Please try again.';
    anneChatHistory.push({ role: 'assistant', content: reply });

    const aiWrap = document.createElement('div');
    aiWrap.className = 'anne-msg-wrap-ai';
    aiWrap.innerHTML = `
      <div class="anne-msg-bubble anne-msg-ai">${reply}</div>
      <div class="anne-msg-time">${now}</div>
    `;
    area.appendChild(aiWrap);
  } catch {
    typingWrap.remove();
    const errWrap = document.createElement('div');
    errWrap.className = 'anne-msg-wrap-ai';
    errWrap.innerHTML = `<div class="anne-msg-bubble anne-msg-ai">Connection error. Please try again.</div>`;
    area.appendChild(errWrap);
  }

  area.scrollTop = area.scrollHeight;
}
