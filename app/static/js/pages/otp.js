// halaman OTP: input cuma boleh angka + tombol kirim ulang ada hitung mundurnya
(function () {
  "use strict";

  const otpInput = document.getElementById("otp_code");
  const resendButton = document.getElementById("resend_button");

  // langsung fokus ke kolom OTP, user tinggal ngetik
  if (otpInput) {
    const maxCodeLength = otpInput.maxLength > 0 ? otpInput.maxLength : 6;
    // webmail selalu buka tombol email di tab baru: kode dioper ke tab ALR yg lagi nunggu OTP biar ga dobel tab
    const otpChannel = "BroadcastChannel" in window ? new BroadcastChannel("alr-otp") : null;
    if (otpChannel) {
      otpChannel.onmessage = function (event) {
        const data = event.data || {};
        if (data.path !== window.location.pathname) {
          return;
        }
        if (data.code && /^\d+$/.test(data.code)) {
          otpInput.value = data.code.slice(0, maxCodeLength);
          otpInput.focus();
          otpChannel.postMessage({ path: data.path, received: true });
        } else if (data.received) {
          // tab lama udah keisi: tutup tab ini, kalau browser nolak kasih tau user
          window.close();
          showOtherTabNotice();
        }
      };
    }

    // dari tombol "Isi Kode Otomatis" di email (#code=123456): isi kolom, lalu hapus kode dari address bar
    const hashCode = new URLSearchParams(window.location.hash.slice(1)).get("code");
    if (hashCode && /^\d+$/.test(hashCode)) {
      otpInput.value = hashCode.slice(0, maxCodeLength);
      history.replaceState(null, "", window.location.pathname + window.location.search);
      if (otpChannel) {
        otpChannel.postMessage({ path: window.location.pathname, code: hashCode });
      }
    }
    otpInput.focus();

    // buang selain angka (termasuk pas paste), potong sesuai maxlength
    otpInput.addEventListener("input", function () {
      otpInput.value = otpInput.value.replace(/\D/g, "").slice(0, maxCodeLength);
    });
  }

  function showOtherTabNotice() {
    const formEl = otpInput.closest("form");
    if (!formEl || document.getElementById("otp_other_tab_notice")) {
      return;
    }
    const noticeEl = document.createElement("div");
    noticeEl.id = "otp_other_tab_notice";
    noticeEl.className = "alert alert-success";
    noticeEl.setAttribute("role", "status");
    noticeEl.textContent = "The code has been filled in your other ALR tab. You can close this tab.";
    formEl.parentNode.insertBefore(noticeEl, formEl);
  }

  // tombol kirim ulang dikunci dulu selama jeda
  if (resendButton) {
    const originalLabel = resendButton.textContent;
    let remainingSeconds = parseInt(resendButton.dataset.cooldownSeconds, 10) || 0;
    let timerId = null;

    function updateResendButton() {
      if (remainingSeconds <= 0) {
        resendButton.disabled = false;
        resendButton.textContent = originalLabel;
        if (timerId) {
          clearInterval(timerId);
        }
        return;
      }
      resendButton.disabled = true;
      resendButton.textContent = originalLabel + " (" + remainingSeconds + "s)";
      remainingSeconds -= 1;
    }

    updateResendButton();
    timerId = setInterval(updateResendButton, 1000);
  }
})();