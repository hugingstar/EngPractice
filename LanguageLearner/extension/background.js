chrome.action.onClicked.addListener(async (tab) => {
  // Check if current URL is a YouTube video
  const url = tab.url;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  const videoId = (match && match[2].length === 11) ? match[2] : null;

  if (!videoId) {
    chrome.tabs.create({ url: `http://localhost:8000/` });
    return;
  }

  // 1. YouTube 페이지에서 자막 데이터 추출 시도
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN',
      func: async () => {
        const response = window.ytInitialPlayerResponse;
        const captionTracks = response?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
        if (!captionTracks.length) {
          return { videoId: response?.videoDetails?.videoId || null, transcripts: [] };
        }

        const transcripts = [];
        for (const track of captionTracks) {
          try {
            const res = await fetch(track.baseUrl + "&fmt=json3");
            if (res.ok) {
              const data = await res.json();
              transcripts.push({
                lang: track.languageCode,
                captionJson: data
              });
            }
          } catch (e) {
            console.error("Failed to fetch track: " + track.languageCode, e);
          }
        }
        return {
          videoId: response?.videoDetails?.videoId || null,
          transcripts: transcripts
        };
      }
    });

    const extractionResult = results?.[0]?.result;
    if (extractionResult && extractionResult.transcripts && extractionResult.transcripts.length > 0) {
      // 2. 로컬 서버에 전송
      try {
        const postRes = await fetch("http://localhost:8000/api/submit_transcript", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(extractionResult)
        });
        if (postRes.ok) {
          console.log("Transcript cached successfully!");
        } else {
          console.error("Failed to submit transcript:", await postRes.text());
        }
      } catch (e) {
        console.error("Server is not running or failed to connect:", e);
      }
    } else {
      console.warn("No transcripts extracted or window.ytInitialPlayerResponse not ready.");
    }
  } catch (e) {
    console.error("Failed to execute scripting or extract transcript:", e);
  }

  // 3. 앱 열기
  chrome.tabs.create({ url: `http://localhost:8000/?videoId=${videoId}` });
});
