const DEFAULT_BACKEND_URL = 'https://ggeolmu-language.onrender.com'; // 사용자님이 배포한 실제 Render 백엔드 주소로 대체됩니다.
let player;
let isPlayerReady = false;
let currentHighlightedIndex = -1;
let currentTranscript = [];
let lastCheckTime = 0; // for rAF throttle

// YouTube open simple web link
function openYouTube() {
  window.open('https://www.youtube.com', '_blank');
}

// Warning banner utility
function showWarningBanner(messages) {
  let banner = document.getElementById('warning-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'warning-banner';
    banner.style.cssText = `
      position: fixed; top: 1rem; left: 50%; transform: translateX(-50%);
      background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.5);
      backdrop-filter: blur(12px); color: #fde68a;
      padding: 0.8rem 1.4rem; border-radius: 12px;
      font-size: 0.9rem; z-index: 9999; max-width: 90vw;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      transition: opacity 0.5s ease;
    `;
    document.body.appendChild(banner);
  }
  banner.innerHTML = messages.map(m => `⚠️ ${m}`).join('<br>');
  banner.style.opacity = '1';
  clearTimeout(banner._hideTimer);
  banner._hideTimer = setTimeout(() => { banner.style.opacity = '0'; }, 5000);
}

// Initialize YouTube API
window.onYouTubeIframeAPIReady = function () {
  // Don't load a video initially
};

function extractVideoId(url) {
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  return (match && match[2].length === 11) ? match[2] : null;
}

function onPlayerReady(event) {
  isPlayerReady = true;
  requestAnimationFrame(checkCurrentTime);
}

// Binary search: find the last transcript item whose startTime <= targetTime
function binarySearchTranscript(targetTime) {
  let lo = 0, hi = currentTranscript.length - 1, result = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (currentTranscript[mid].startTime <= targetTime) {
      result = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return result;
}

function onPlayerStateChange(event) {
  // Handle play/pause states here if needed
}

// Render Transcript
const transcriptContainer = document.getElementById('transcript-container');
const tooltip = document.getElementById('tooltip');
const tooltipPron = document.getElementById('tooltip-pron');
const tooltipMean = document.getElementById('tooltip-mean');

function renderTranscript(transcriptData) {
  transcriptContainer.innerHTML = '';
  currentTranscript = transcriptData;

  if (transcriptData.length === 0) {
    transcriptContainer.innerHTML = '<div class="empty-state">No transcript available for this video.</div>';
    return;
  }

  transcriptData.forEach((line, index) => {
    const lineEl = document.createElement('div');
    lineEl.className = 'transcript-item';
    lineEl.dataset.index = index;

    // Create actions container
    const actionsEl = document.createElement('div');
    actionsEl.className = 'sentence-actions';

    const translateBtn = document.createElement('button');
    translateBtn.className = 'translate-btn';
    translateBtn.textContent = 'A/가';
    translateBtn.title = '누르고 있으면 해석을 봅니다';

    const translationEl = document.createElement('div');
    translationEl.className = 'sentence-translation';
    translationEl.textContent = line.translation || '';

    actionsEl.appendChild(translateBtn);
    actionsEl.appendChild(translationEl);

    // Create text container
    const textEl = document.createElement('div');
    textEl.className = 'sentence-text';

    // Create words with spans for hover
    line.words.forEach(wordObj => {
      // Strip punctuation to check if it's a real word (supports English, Korean, Japanese, Chinese, etc.)
      const cleanWord = wordObj.text.replace(/[^\w\u00C0-\u024F\u4E00-\u9FA5\u3040-\u30FF\uAC00-\uD7AF]+/g, '');
      const wordSpan = document.createElement('span');
      wordSpan.className = 'word-span';
      wordSpan.textContent = wordObj.text + ' ';

      if (cleanWord.length > 0) {
        wordSpan.classList.add('has-meaning');
        wordSpan.addEventListener('mouseenter', (e) => {
          showTooltip(e, cleanWord);
        });
        wordSpan.addEventListener('mouseleave', hideTooltip);
      }

      // Click word to seek to its exact position in the video
      wordSpan.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent block-level click
        if (isPlayerReady && player) {
          const seekTime = wordObj.startTime ?? line.startTime;
          player.seekTo(seekTime, true);
          player.playVideo();
        }
      });

      textEl.appendChild(wordSpan);
    });

    lineEl.appendChild(actionsEl);
    lineEl.appendChild(textEl);

    // Click on empty area of block (not a word) → jump to block start
    lineEl.addEventListener('click', () => {
      if (isPlayerReady && player) {
        player.seekTo(line.startTime, true);
        player.playVideo();
      }
    });

    transcriptContainer.appendChild(lineEl);
  });
}

// Tooltip positioning & lock state
let tooltipCache = {};
let currentHoverWord = '';
let isTooltipLocked = false;

async function showTooltip(e, word, isDrag = false) {
  const targetLang = document.getElementById('dict-lang')?.value || 'ko';
  currentHoverWord = word;

  if (isDrag) {
    isTooltipLocked = true;
  }

  tooltipPron.textContent = '';
  tooltipMean.textContent = '번역 중...';
  tooltip.classList.remove('hidden');

  const updatePosition = () => {
    let rect;
    if (isDrag) {
      const selection = window.getSelection();
      if (selection && selection.rangeCount > 0) {
        rect = selection.getRangeAt(0).getBoundingClientRect();
      }
    }
    if (!rect && e && e.target) {
      rect = e.target.getBoundingClientRect();
    }
    if (!rect) return;

    const tooltipRect = tooltip.getBoundingClientRect();

    let top = rect.top - tooltipRect.height - 10;
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

    if (top < 0) top = rect.bottom + 10;
    if (left < 0) left = 10;
    if (left + tooltipRect.width > window.innerWidth) left = window.innerWidth - tooltipRect.width - 10;

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
  };

  updatePosition();

  const cacheKey = `${word}_${targetLang}`;
  if (tooltipCache[cacheKey]) {
    const cached = tooltipCache[cacheKey];
    tooltipMean.textContent = cached.text;
    tooltipPron.textContent = cached.pron || '';
    updatePosition();
    return;
  }

  try {
    // dt=rm adds transliteration/reading (furigana romaji / pinyin) to response
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${targetLang}&dt=t&dt=rm&q=${encodeURIComponent(word)}`;
    const res = await fetch(url);
    const data = await res.json();
    const translatedText = data[0][0][0];
    const pronunciation = data[0]?.[0]?.[2] || '';  // reading (romaji / pinyin)

    // Only show pronunciation for languages with complex characters
    const showPron = ['ja', 'zh'].includes(targetLang);

    tooltipCache[cacheKey] = { text: translatedText, pron: showPron ? pronunciation : '' };

    // Only update if we're still hovering/selecting the same text
    if (currentHoverWord === word) {
      tooltipMean.textContent = translatedText;
      tooltipPron.textContent = showPron ? pronunciation : '';
      updatePosition();
    }
  } catch (err) {
    if (currentHoverWord === word) {
      tooltipMean.textContent = '번역 실패';
      updatePosition();
    }
  }
}

function hideTooltip() {
  if (isTooltipLocked) return;
  tooltip.classList.add('hidden');
}

// Drag & Drop phrase translation
document.addEventListener('mouseup', (e) => {
  const selection = window.getSelection();
  const selectedText = selection.toString().trim();

  if (selectedText.length > 0 && selectedText.length < 100) {
    showTooltip(e, selectedText, true);
  }
});

document.addEventListener('mousedown', (e) => {
  // Hide tooltip when clicking outside the tooltip itself
  if (tooltip && !tooltip.contains(e.target)) {
    isTooltipLocked = false;
    tooltip.classList.add('hidden');
  }
});

// Highlight logic — throttled to ~4 times/sec (250ms) to reduce IFrame bridge overhead
function checkCurrentTime(now) {
  if (!isPlayerReady || !player) return;
  requestAnimationFrame(checkCurrentTime);

  // Throttle: only run every 250ms
  if (now - lastCheckTime < 250) return;
  lastCheckTime = now;

  if (player.getPlayerState() !== YT.PlayerState.PLAYING) return;

  const PRE_ROLL_OFFSET = 0.5;
  const targetTime = player.getCurrentTime() + PRE_ROLL_OFFSET;

  // Binary search instead of linear scan
  const foundIndex = binarySearchTranscript(targetTime);

  if (foundIndex !== currentHighlightedIndex) {
    if (currentHighlightedIndex !== -1) {
      const oldEl = transcriptContainer.children[currentHighlightedIndex];
      if (oldEl) oldEl.classList.remove('active');
    }
    if (foundIndex !== -1) {
      const newEl = transcriptContainer.children[foundIndex];
      if (newEl) {
        newEl.classList.add('active');
        // instant scroll avoids continuous layout recalc from smooth animation
        newEl.scrollIntoView({ behavior: 'instant', block: 'center' });
      }
    }
    currentHighlightedIndex = foundIndex;
  }
}

// Load Video & Transcript Logic
document.getElementById('load-btn').addEventListener('click', async () => {
  const urlInput = document.getElementById('video-url').value;
  const videoId = extractVideoId(urlInput);
  const scriptLang = document.getElementById('script-lang')?.value || 'en';
  const dictLang = document.getElementById('dict-lang')?.value || 'ko';

  if (!videoId) {
    alert("Invalid YouTube URL");
    return;
  }

  // 1. Show UI sections if they were hidden
  const welcomeMsg = document.getElementById('welcome-message');
  if (welcomeMsg) welcomeMsg.style.display = 'none';

  document.querySelector('.video-section').style.display = 'flex';
  document.querySelector('.transcript-section').style.display = 'flex';

  // 2. Initialize or Update Player
  if (!player) {
    player = new YT.Player('youtube-player', {
      height: '100%',
      width: '100%',
      videoId: videoId,
      playerVars: { 'playsinline': 1, 'rel': 0 },
      events: {
        'onReady': onPlayerReady,
        'onStateChange': onPlayerStateChange
      }
    });
  } else if (isPlayerReady) {
    player.loadVideoById(videoId);
  }

  currentHighlightedIndex = -1;

  // 3. Fetch Transcript from Backend
  transcriptContainer.innerHTML = '<div class="loading-spinner">Loading transcript...</div>';

  try {
    const urlParams = new URLSearchParams(window.location.search);
    const backendParam = urlParams.get('backend') || '';

    let apiBase = '';
    let apiPath = '/api/transcript';

    if (backendParam) {
      apiBase = backendParam.replace(/\/$/, '');
    } else if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      // Netlify 배포 사이트에서 접속하면 사용자가 배포한 Render 백엔드로 자동 연동
      apiBase = DEFAULT_BACKEND_URL;
      apiPath = '/api/transcript';
    }

    const response = await fetch(`${apiBase}${apiPath}?videoId=${videoId}&scriptLang=${scriptLang}&dictLang=${dictLang}`);

    // Check if the response is actually JSON (to prevent 'Unexpected token <' from HTML error pages)
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      throw new Error("서버 통신 오류: 로컬 자막 전용 서버(포트 8000번)가 실행 중인지 확인해주세요.");
    }

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "자막을 불러오는데 실패했습니다.");
    }

    const data = await response.json();

    // Show warning banner if server returned any warnings
    if (data.warnings && data.warnings.length > 0) {
      showWarningBanner(data.warnings);
    }

    // Extract transcript array from new response shape
    const transcript = data.transcript || data;
    renderTranscript(transcript);
  } catch (error) {
    console.error(error);
    transcriptContainer.innerHTML = `<div class="empty-state">❌ ${error.message}</div>`;
  }
});

// Auto-load if videoId is in the URL (Bookmarklet support)
document.addEventListener('DOMContentLoaded', () => {
  // Bind click listener for open youtube button
  document.getElementById('open-youtube-btn')?.addEventListener('click', openYouTube);

  // Dynamically bake the current host domain (origin) into the bookmarklet href
  const bookmarkletBtn = document.getElementById('bookmarklet-btn');
  if (bookmarkletBtn) {
    const currentOrigin = window.location.origin;
    const rawCode = bookmarkletBtn.getAttribute('href');
    if (rawCode) {
      const updatedCode = rawCode.replace('http://localhost:8000', currentOrigin);
      bookmarkletBtn.setAttribute('href', updatedCode);
    }
  }

  const params = new URLSearchParams(window.location.search);
  const videoIdParam = params.get('videoId');
  if (videoIdParam) {
    // Fill the input and trigger the load button
    document.getElementById('video-url').value = `https://youtu.be/${videoIdParam}`;
    document.getElementById('load-btn').click();
  }
});
