document.addEventListener('DOMContentLoaded', () => {
  const authBtn = document.getElementById('auth-btn');
  const authModal = document.getElementById('auth-modal');
  const closeModal = document.getElementById('close-modal');
  
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const toggleToRegister = document.getElementById('toggle-to-register');
  const toggleToLogin = document.getElementById('toggle-to-login');
  
  const loginSubmit = document.getElementById('login-submit');
  const regSubmit = document.getElementById('reg-submit');
  
  const authSuccessContainer = document.getElementById('auth-success-container');
  const authUniqueCode = document.getElementById('auth-unique-code');
  const authOkBtn = document.getElementById('auth-ok-btn');
  const authFormContainer = document.getElementById('auth-form-container');
  const modalError = document.getElementById('modal-error');

  const mainAppContainer = document.getElementById('main-app-container');
  let isAuthenticated = false;

  // Check auth state on load
  fetch('/api/users/check/')
    .then(r => r.json())
    .then(data => {
      if (data.is_authenticated) {
        isAuthenticated = true;
        const userInfo = document.getElementById('user-info-display');
        userInfo.textContent = `${data.username} (${data.name})`;
        userInfo.style.display = 'inline-block';
        authBtn.textContent = '로그아웃';
        mainAppContainer.style.display = 'block';
        authModal.classList.add('hidden');
        closeModal.style.display = 'block';
      } else {
        // Not authenticated, modal is already shown by default
        showLogin();
      }
    });

  authBtn.addEventListener('click', () => {
    if (isAuthenticated) {
      // Logout
      fetch('/api/users/logout/')
        .then(() => {
          isAuthenticated = false;
          window.location.reload();
        });
    } else {
      // Open modal
      authModal.classList.remove('hidden');
      modalError.textContent = '';
      showLogin();
    }
  });

  closeModal.addEventListener('click', () => {
    authModal.classList.add('hidden');
  });

  authOkBtn.addEventListener('click', () => {
    authModal.classList.add('hidden');
    window.location.reload();
  });

  toggleToRegister.addEventListener('click', (e) => {
    e.preventDefault();
    showRegister();
  });

  toggleToLogin.addEventListener('click', (e) => {
    e.preventDefault();
    showLogin();
  });

  function showLogin() {
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
    authSuccessContainer.style.display = 'none';
    authFormContainer.style.display = 'block';
    modalError.textContent = '';
  }

  function showRegister() {
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
    authSuccessContainer.style.display = 'none';
    authFormContainer.style.display = 'block';
    modalError.textContent = '';
  }

  function showSuccess(code) {
    authFormContainer.style.display = 'none';
    authSuccessContainer.style.display = 'block';
    authUniqueCode.textContent = "고유코드: " + code;
    modalError.textContent = '';
  }

  const handleLoginEnter = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      loginSubmit.click();
    }
  };

  document.getElementById('login-username').addEventListener('keypress', handleLoginEnter);
  document.getElementById('login-password').addEventListener('keypress', handleLoginEnter);

  const handleRegEnter = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      regSubmit.click();
    }
  };
  
  document.getElementById('reg-name').addEventListener('keypress', handleRegEnter);
  document.getElementById('reg-username').addEventListener('keypress', handleRegEnter);
  document.getElementById('reg-password').addEventListener('keypress', handleRegEnter);

  loginSubmit.addEventListener('click', async () => {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    if(!username || !password) {
      modalError.textContent = "아이디와 비밀번호를 입력해주세요.";
      return;
    }

    try {
      const res = await fetch('/api/users/login/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
      });
      
      let data;
      try {
        data = await res.json();
      } catch (parseError) {
        throw new Error("서버에서 올바르지 않은 응답이 반환되었습니다. (오류 메시지: Not Found가 반환되었을 수 있습니다.)");
      }

      if(res.ok) {
        isAuthenticated = true;
        showSuccess(data.unique_code);
      } else {
        modalError.textContent = data.error || "로그인 실패";
      }
    } catch (e) {
      modalError.textContent = "오류 발생: " + e.message;
    }
  });

  regSubmit.addEventListener('click', async () => {
    const name = document.getElementById('reg-name').value;
    const username = document.getElementById('reg-username').value;
    const password = document.getElementById('reg-password').value;
    
    if(!name || !username || !password) {
      modalError.textContent = "모든 필드를 입력해주세요.";
      return;
    }

    try {
      const res = await fetch('/api/users/register/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password, name})
      });

      let data;
      try {
        data = await res.json();
      } catch (parseError) {
        throw new Error("서버에서 올바르지 않은 응답이 반환되었습니다. (오류 메시지: Not Found가 반환되었을 수 있습니다.)");
      }

      if(res.ok) {
        // 회원가입 성공
        showSuccess(data.unique_code);
      } else {
        modalError.textContent = data.error || "회원가입 실패";
      }
    } catch (e) {
      modalError.textContent = "오류 발생: " + e.message;
    }
  });
});
