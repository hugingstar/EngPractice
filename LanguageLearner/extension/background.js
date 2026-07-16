chrome.action.onClicked.addListener(async (tab) => {
  // Check if current URL is a YouTube video
  const url = tab.url;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  const videoId = (match && match[2].length === 11) ? match[2] : null;

  if (!videoId) {
    chrome.windows.create({
      url: `http://ggeolmu-language.com/`,
      type: 'popup',
      width: 1200,
      height: 800
    });
    return;
  }

  // 1. YouTube 페이지에서 자막 데이터 추출 시도
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN',
      func: async () => {
        let response = null;
        try {
          const player = document.getElementById('movie_player');
          if (player && typeof player.getPlayerResponse === 'function') {
            response = player.getPlayerResponse();
          }
        } catch (e) {
          console.error("Failed to get movie_player response", e);
        }
        if (!response) {
          response = window.ytInitialPlayerResponse;
        }

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
        const postRes = await fetch("http://ggeolmu-language.com/api/submit_transcript", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ videoId, transcripts: extractionResult.transcripts })
        });
        const resText = await postRes.text();
        console.log("Submit response:", resText);
      } catch (err) {
        console.error("Submit error:", err);
      }
    } else {
      // 자막을 하나도 못 뽑아온 경우
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => alert("이 유튜브 영상에는 추출할 수 있는 캡션(자막)이 없습니다.")
      });
      return; // 앱을 열지 않고 종료
    }
  } catch (e) {
    console.error("Failed to execute scripting or extract transcript:", e);
  }

  // 3. 앱 형태의 독립된 팝업 창 열기
  chrome.windows.create({
    url: `http://ggeolmu-language.com/?videoId=${videoId}`,
    type: 'popup',
    width: 1200,
    height: 800
  });
});
