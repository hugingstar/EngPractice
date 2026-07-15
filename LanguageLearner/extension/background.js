chrome.action.onClicked.addListener((tab) => {
  // Check if current URL is a YouTube video
  const url = tab.url;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  const videoId = (match && match[2].length === 11) ? match[2] : null;

  if (videoId) {
    // Open Language Learner Pro with the videoId
    chrome.tabs.create({ url: `http://localhost:8000/?videoId=${videoId}` });
  } else {
    // Not a YouTube video? Just open the app
    chrome.tabs.create({ url: `http://localhost:8000/` });
  }
});
