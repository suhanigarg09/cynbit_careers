
document.addEventListener("DOMContentLoaded", function () {

    // Prevent accidental double submission.
    const forms = document.querySelectorAll("form");

    forms.forEach(function (form) {

        form.addEventListener("submit", function () {

            const button = form.querySelector(
                'button[type="submit"]'
            );

            if (button && form.checkValidity()) {
                button.disabled = true;
                button.textContent = "Please wait...";
            }

        });

    });

    // Show selected resume filename.
    const resumeInput = document.querySelector(
        'input[name="resume"]'
    );

    if (resumeInput) {

        resumeInput.addEventListener("change", function () {

            const file = this.files[0];

            if (file && file.size > 5 * 1024 * 1024) {
                alert("Please select a PDF smaller than 5 MB.");
                this.value = "";
            }

        });

    }

});
