document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById("fileInput");
    const fileNamePreview = document.getElementById("fileNamePreview");
    const uploadBox = document.getElementById("uploadBox");
    const uploadForm = document.getElementById("uploadForm");
    const flashContainer = document.getElementById("flashContainer");

    if (fileInput && fileNamePreview) {
        fileInput.addEventListener("change", () => {
            const file = fileInput.files[0];

            if (!file) {
                fileNamePreview.textContent = "";
                return;
            }

            const maxSize = 2 * 1024 * 1024;

            if (file.size > maxSize) {
                fileNamePreview.textContent = "File is larger than 2 MB.";
                fileNamePreview.classList.add("file-error");
                fileInput.value = "";
                return;
            }

            fileNamePreview.classList.remove("file-error");
            fileNamePreview.textContent = `Selected: ${file.name}`;
        });
    }

    // Drag & drop selects the file only; upload still happens through the submit button.
    if (uploadBox && fileInput) {
        ["dragenter", "dragover"].forEach(eventName => {
            uploadBox.addEventListener(eventName, event => {
                event.preventDefault();
                uploadBox.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(eventName => {
            uploadBox.addEventListener(eventName, event => {
                event.preventDefault();
                uploadBox.classList.remove("dragover");
            });
        });

        uploadBox.addEventListener("drop", event => {
            const files = event.dataTransfer.files;
            if (!files.length) return;

            fileInput.files = files;
            fileInput.dispatchEvent(new Event("change"));
        });
    }

    if (uploadForm) {
        uploadForm.addEventListener("submit", event => {
            if (!fileInput || !fileInput.files.length) {
                event.preventDefault();
                alert("Please select a file first.");
                return;
            }

            const button = document.getElementById("uploadButton");
            if (button) {
                button.disabled = true;
                button.textContent = "Uploading...";
            }
        });
    }

    // Auto-hide flash messages after 3 seconds.
    if (flashContainer) {
        setTimeout(() => {
            flashContainer.classList.add("hide");
        }, 3000);
    }

    // Login/register password visibility.
    const togglePassword = document.getElementById("togglePassword");
    const password = document.getElementById("password");

    if (togglePassword && password) {
        togglePassword.addEventListener("click", () => {
            const visible = password.type === "text";
            password.type = visible ? "password" : "text";
            togglePassword.textContent = visible ? "Show" : "Hide";
        });
    }

    // Keep the stored-files section in view after filtering.
    const filterForm = document.getElementById("filterForm");
    if (filterForm && window.location.search) {
        setTimeout(() => {
            const storedFiles = document.getElementById("storedFiles");
            if (storedFiles) {
                storedFiles.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }, 100);
    }
});
