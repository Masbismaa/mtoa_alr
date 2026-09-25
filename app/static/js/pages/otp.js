// halaman OTP: input cuma boleh angka + tombol kirim ulang ada hitung mundurnya
(function () {
  "use strict";

  const otpInput = document.getElementById("otp_code");
  const resendButton = document.getElementById("resend_button");

  // langsung fokus ke kolom OTP, user tinggal ngetik
  if (otpInput) {
    otpInput.focus();

    // buang selain angka (termasuk pas paste), potong sesuai maxlength
    otpInput.addEventListener("input", function () {
      const maxLength = otpInput.maxLength > 0 ? otpInput.maxLength : 6;
      otpInput.value = otpInput.value.replace(/\D/g, "").slice(0, maxLength);
    });
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
      resendButton.textContent = originalLabel + " (" + remainingSeconds + " dtk)";
      remainingSeconds -= 1;
    }

    updateResendButton();
    timerId = setInterval(updateResendButton, 1000);
  }
})();