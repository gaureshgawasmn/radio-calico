const STREAM_URL   = 'https://d3d4yli4hf5bmh.cloudfront.net/hls/live.m3u8';
const METADATA_URL = 'https://d3d4yli4hf5bmh.cloudfront.net/metadatav2.json';
const COVER_URL    = 'https://d3d4yli4hf5bmh.cloudfront.net/cover.jpg';
const POLL_MS      = 10000;

const audio        = document.getElementById('audio');
const playBtn      = document.getElementById('playBtn');
const volumeSlider = document.getElementById('volume');
const volIcon      = document.getElementById('volIcon');
const statusDot    = document.getElementById('statusDot');
const statusText   = document.getElementById('statusText');
const visualizer   = document.getElementById('visualizer');
const coverWrap    = document.getElementById('coverWrap');
const npCover      = document.getElementById('npCover');
const yearBadge    = document.getElementById('yearBadge');
const npArtist     = document.getElementById('npArtist');
const npTitle      = document.getElementById('npTitle');
const npAlbum      = document.getElementById('npAlbum');
const srcQuality   = document.getElementById('srcQuality');
const recentList   = document.getElementById('recentList');

// ── Equalizer bars ──────────────────────────────────────────────────────
const BAR_COUNT = 22;
const bars = [];
for (let i = 0; i < BAR_COUNT; i++) {
  const b = document.createElement('div');
  b.className = 'bar';
  b.style.setProperty('--max-h', (6 + Math.random() * 16) + 'px');
  b.style.setProperty('--dur',   (0.4 + Math.random() * 0.6).toFixed(2) + 's');
  b.style.animationDelay = (Math.random() * 0.4).toFixed(2) + 's';
  visualizer.appendChild(b);
  bars.push(b);
}

// ── Status ───────────────────────────────────────────────────────────────
function setStatus(state) {
  statusDot.className  = 'status-pip '   + state;
  statusText.className = 'status-label ' + state;
  const labels = { live: 'On Air', buffering: 'Buffering…', error: 'Error', '': 'Offline' };
  statusText.textContent = labels[state] ?? 'Offline';
}

function setEq(active) {
  bars.forEach(b => b.classList.toggle('active', active));
}

// ── Cover art ────────────────────────────────────────────────────────────
function reloadCover() {
  coverWrap.classList.remove('art-loaded');
  npCover.classList.remove('loaded');
  const img = new Image();
  img.onload = () => {
    npCover.src = img.src;
    npCover.classList.add('loaded');
    coverWrap.classList.add('art-loaded');
  };
  img.onerror = () => coverWrap.classList.add('art-loaded');
  img.src = COVER_URL + '?_=' + Date.now();
}

// ── Metadata ─────────────────────────────────────────────────────────────
let lastTitle = null;

function truncate(str, max) {
  return str && str.length > max ? str.slice(0, max - 1) + '…' : str;
}

function fmtQuality(bit_depth, sample_rate) {
  if (!bit_depth && !sample_rate) return '—';
  const khz = sample_rate ? (sample_rate / 1000).toFixed(1) + ' kHz' : '';
  const bit = bit_depth  ? bit_depth + ' bit' : '';
  return [bit, khz].filter(Boolean).join(' / ');
}

async function fetchMetadata() {
  try {
    const res  = await fetch(METADATA_URL + '?_=' + Date.now());
    if (!res.ok) return;
    const data = await res.json();

    const title  = data.title  || 'Unknown Title';
    const artist = data.artist || 'Unknown Artist';

    if (title === lastTitle) return;
    lastTitle = title;

    reloadCover();
    resetRatings();
    currentSong = title;
    fetchRatings(title);

    npArtist.textContent = truncate(artist, 50);
    npTitle.textContent  = truncate(title, 60) + (data.is_new ? ' ★' : '');
    npAlbum.textContent  = truncate(data.album || '', 70) || '—';
    srcQuality.textContent = fmtQuality(data.bit_depth, data.sample_rate);

    if (data.date) {
      yearBadge.textContent = data.date;
      yearBadge.classList.add('visible');
    } else {
      yearBadge.classList.remove('visible');
    }

    // Fade in info col
    const infoCol = document.querySelector('.info-col');
    infoCol.classList.remove('fade-in');
    void infoCol.offsetWidth;
    infoCol.classList.add('fade-in');

    // Recently Played
    const tracks = [];
    for (let i = 1; i <= 5; i++) {
      const a = data[`prev_artist_${i}`];
      const t = data[`prev_title_${i}`];
      if (a || t) tracks.push({ artist: a || '—', title: t || '—' });
    }

    recentList.innerHTML = '';
    if (!tracks.length) {
      recentList.innerHTML = '<li class="recent-item" style="color:#8aac8b;font-size:11px;">No history yet</li>';
      return;
    }

    tracks.forEach((track, idx) => {
      const li = document.createElement('li');
      li.className = 'recent-item fade-in';
      li.style.animationDelay = (idx * 0.05) + 's';
      li.innerHTML =
        `<span class="recent-num">${idx + 1}</span>` +
        `<span class="recent-title">${escHtml(truncate(track.title, 45))}</span>` +
        `<span class="recent-artist">${escHtml(truncate(track.artist, 35))}</span>`;
      recentList.appendChild(li);
    });

  } catch (_) {}
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Ratings ──────────────────────────────────────────────────────────────
const btnUp     = document.getElementById('btnUp');
const btnDown   = document.getElementById('btnDown');
const countUp   = document.getElementById('countUp');
const countDown = document.getElementById('countDown');
let   currentSong = null;

function applyRatingState({ ups, downs, user_vote }) {
  countUp.textContent   = ups;
  countDown.textContent = downs;
  btnUp.classList.toggle('voted-up',    user_vote === 'up');
  btnDown.classList.toggle('voted-down', user_vote === 'down');
  btnUp.disabled = btnDown.disabled = false;
}

function resetRatings() {
  currentSong = null;
  countUp.textContent = countDown.textContent = '—';
  btnUp.classList.remove('voted-up');
  btnDown.classList.remove('voted-down');
  btnUp.disabled = btnDown.disabled = true;
}

async function fetchRatings(song) {
  try {
    const res = await fetch(`/api/ratings?song=${encodeURIComponent(song)}`);
    if (res.ok) applyRatingState(await res.json());
  } catch (_) {}
}

async function castVote(vote) {
  if (!currentSong) return;
  btnUp.disabled = btnDown.disabled = true;
  try {
    const res = await fetch('/api/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ song: currentSong, vote }),
    });
    if (res.ok) applyRatingState(await res.json());
    else btnUp.disabled = btnDown.disabled = false;
  } catch (_) { btnUp.disabled = btnDown.disabled = false; }
}

btnUp.addEventListener('click',   () => castVote('up'));
btnDown.addEventListener('click', () => castVote('down'));

reloadCover();
fetchMetadata();
setInterval(fetchMetadata, POLL_MS);

// ── HLS Player ───────────────────────────────────────────────────────────
let hls = null;
let playing = false;

function setupHls() {
  if (Hls.isSupported()) {
    hls = new Hls({ enableWorker: true, lowLatencyMode: false });
    hls.loadSource(STREAM_URL);
    hls.attachMedia(audio); // sets audio.src synchronously via URL.createObjectURL

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      audio.volume = parseFloat(volumeSlider.value);
    });

    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data.fatal) {
        setStatus('error');
        setEq(false);
        playing = false;
        playBtn.innerHTML = '&#9654;';
        // Fatal error: full teardown so the next play creates a fresh instance
        hls.destroy();
        hls = null;
      }
    });
  } else if (audio.canPlayType('application/vnd.apple.mpegurl')) {
    audio.src = STREAM_URL;
    audio.volume = parseFloat(volumeSlider.value);
  } else {
    setStatus('error');
    statusText.textContent = 'Unsupported';
  }
}

audio.addEventListener('playing', () => {
  playing = true;
  setStatus('live');
  setEq(true);
  playBtn.innerHTML = '&#9646;&#9646;';
});

audio.addEventListener('waiting', () => setStatus('buffering'));

audio.addEventListener('pause', () => {
  playing = false;
  setStatus('');
  setEq(false);
  playBtn.innerHTML = '&#9654;';
});

playBtn.addEventListener('click', () => {
  if (!playing) {
    setStatus('buffering');
    if (!hls) {
      // First play: create the HLS instance (sets audio.src synchronously)
      setupHls();
    } else {
      // Resume after pause: jump back to live edge without destroying
      // the HLS instance or resetting the audio element
      hls.startLoad(-1);
    }
    audio.volume = parseFloat(volumeSlider.value);
    audio.play().catch(err => {
      setStatus('error');
      console.warn('Playback blocked:', err);
    });
  } else {
    // Stop fetching segments but keep the HLS instance and audio element
    // intact so the next play() call works without needing a new user gesture
    if (hls) hls.stopLoad();
    audio.pause();
  }
});

volumeSlider.addEventListener('input', () => {
  const v = parseFloat(volumeSlider.value);
  audio.volume = v;
  volIcon.textContent = v === 0 ? '🔇' : v < 0.5 ? '🔈' : '🔊';
});
