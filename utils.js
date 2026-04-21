function truncate(str, max) {
  return str && str.length > max ? str.slice(0, max - 1) + '…' : str;
}

function fmtQuality(bit_depth, sample_rate) {
  if (!bit_depth && !sample_rate) return '—';
  const khz = sample_rate ? (sample_rate / 1000).toFixed(1) + ' kHz' : '';
  const bit = bit_depth  ? bit_depth + ' bit' : '';
  return [bit, khz].filter(Boolean).join(' / ');
}

function fmtStreamLevel(level) {
  if (!level) return '—';
  const codecMap = { mp4a: 'AAC', alac: 'ALAC', 'ac-3': 'AC-3', 'ec-3': 'E-AC-3', fLaC: 'FLAC' };
  const rawCodec = (level.audioCodec || '').split('.')[0].toLowerCase();
  const codec = codecMap[rawCodec] || (rawCodec ? rawCodec.toUpperCase() : '');
  const kbps = level.bitrate ? Math.round(level.bitrate / 1000) + ' kbps' : '';
  return [codec, kbps].filter(Boolean).join(' ') || '—';
}

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function applyRatingState({ ups, downs, user_vote }, btnUp, btnDown, countUp, countDown) {
  countUp.textContent   = ups;
  countDown.textContent = downs;
  btnUp.classList.toggle('voted-up',    user_vote === 'up');
  btnDown.classList.toggle('voted-down', user_vote === 'down');
  btnUp.disabled = btnDown.disabled = false;
}

function resetRatings(btnUp, btnDown, countUp, countDown) {
  countUp.textContent = countDown.textContent = '—';
  btnUp.classList.remove('voted-up');
  btnDown.classList.remove('voted-down');
  btnUp.disabled = btnDown.disabled = true;
}

if (typeof module !== 'undefined') {
  module.exports = { truncate, fmtQuality, fmtStreamLevel, escHtml, applyRatingState, resetRatings };
}
