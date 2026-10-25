document.addEventListener("DOMContentLoaded", function () {

    const fileInput = document.getElementById("fileInput");
    const uploadBox = document.getElementById("uploadBox");
    const fileNamePreview = document.getElementById("fileNamePreview");

    if (!fileInput || !uploadBox) {
        return;
    }

    const maxSize = 2 * 1024 * 1024;

    const allowedExtensions = [
        "jpg",
        "jpeg",
        "png",
        "pdf",
        "mp4",
        "ppt",
        "pptx"
    ];

    function showFile(file) {

        if (!file) {
            return;
        }

        const fileName = file.name;
        const extension = fileName
            .split(".")
            .pop()
            .toLowerCase();

        // Check file type
        if (!allowedExtensions.includes(extension)) {

            alert(
                "File type not supported.\n\n" +
                "Allowed: JPG, JPEG, PNG, PDF, MP4, PPT, PPTX"
            );

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "";
            }

            return;
        }

        // Check file size
        if (file.size > maxSize) {

            alert("File size must be less than 2 MB.");

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "";
            }

            return;
        }

        // Show selected file
        if (fileNamePreview) {
            fileNamePreview.textContent =
                "Selected: " + fileName;
        }
    }

    // File selected normally
    fileInput.addEventListener("change", function () {

        const file = this.files[0];

        showFile(file);
    });

    // Open file selector when clicking upload area
    uploadBox.addEventListener("click", function (event) {

        if (
            event.target.tagName !== "INPUT" &&
            !event.target.closest(".file-select-btn")
        ) {
            fileInput.click();
        }
    });

    // Drag over
    uploadBox.addEventListener("dragover", function (event) {

        event.preventDefault();

        uploadBox.classList.add("dragover");
    });

    // Drag leave
    uploadBox.addEventListener("dragleave", function () {

        uploadBox.classList.remove("dragover");
    });

    // File dropped
    uploadBox.addEventListener("drop", function (event) {

        event.preventDefault();

        uploadBox.classList.remove("dragover");

        const files = event.dataTransfer.files;

        if (files.length > 0) {

            const file = files[0];

            try {
                const dataTransfer = new DataTransfer();

                dataTransfer.items.add(file);

                fileInput.files = dataTransfer.files;

            } catch (error) {
                console.log("Could not assign dropped file.");
            }

            showFile(file);
        }
    });

});