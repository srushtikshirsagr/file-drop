document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // ELEMENTS
    // =========================================================

    const fileInput =
        document.getElementById("fileInput");

    const uploadBox =
        document.getElementById("uploadBox");

    const uploadForm =
        document.getElementById("uploadForm");

    const uploadButton =
        document.getElementById("uploadButton");

    const fileNamePreview =
        document.getElementById("fileNamePreview");

    const uploadStatus =
        document.getElementById("uploadStatus");

    const storedFiles =
        document.getElementById("storedFiles");

    const filterForm =
        document.getElementById("filterForm");


    // =========================================================
    // SETTINGS
    // =========================================================

    const maxSize =
        2 * 1024 * 1024;


    const allowedExtensions = [
        "jpg",
        "jpeg",
        "png",
        "pdf",
        "mp4",
        "ppt",
        "pptx"
    ];


    // =========================================================
    // SHOW STATUS
    // =========================================================

    function showUploadStatus(message, type = "success") {

        if (!uploadStatus) {
            return;
        }

        uploadStatus.textContent = message;

        uploadStatus.className =
            "upload-status " + type;

        setTimeout(function () {

            uploadStatus.textContent = "";

            uploadStatus.className =
                "upload-status";

        }, 3000);
    }


    // =========================================================
    // FILE VALIDATION
    // =========================================================

    function validateFile(file) {

        if (!file) {
            return false;
        }


        const fileName =
            file.name;


        const extension =
            fileName
                .split(".")
                .pop()
                .toLowerCase();


        // FILE TYPE

        if (!allowedExtensions.includes(extension)) {

            showUploadStatus(
                "File type is not supported.",
                "error"
            );

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "";
            }

            return false;
        }


        // FILE SIZE

        if (file.size > maxSize) {

            showUploadStatus(
                "File size must be less than 2 MB.",
                "error"
            );

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "";
            }

            return false;
        }


        return true;
    }


    // =========================================================
    // DISPLAY SELECTED FILE
    // =========================================================

    function showFile(file) {

        if (!validateFile(file)) {
            return;
        }


        if (fileNamePreview) {

            const sizeMB =
                (
                    file.size /
                    1024 /
                    1024
                ).toFixed(2);


            fileNamePreview.innerHTML =
                `
                <span class="selected-file-icon">✓</span>
                <strong>${escapeHtml(file.name)}</strong>
                <span>(${sizeMB} MB)</span>
                `;
        }


        showUploadStatus(
            "File selected. Ready to upload.",
            "success"
        );
    }


    // =========================================================
    // ESCAPE HTML
    // =========================================================

    function escapeHtml(text) {

        const div =
            document.createElement("div");

        div.textContent =
            text;

        return div.innerHTML;
    }


    // =========================================================
    // FILE PICKER
    // =========================================================

    if (fileInput) {

        fileInput.addEventListener(
            "change",
            function () {

                const file =
                    this.files[0];

                showFile(file);

            }
        );
    }


    // =========================================================
    // DRAG AND DROP
    // =========================================================

    if (uploadBox) {

        uploadBox.addEventListener(
            "dragover",
            function (event) {

                event.preventDefault();

                uploadBox.classList.add(
                    "dragover"
                );
            }
        );


        uploadBox.addEventListener(
            "dragleave",
            function () {

                uploadBox.classList.remove(
                    "dragover"
                );
            }
        );


        uploadBox.addEventListener(
            "drop",
            function (event) {

                event.preventDefault();

                uploadBox.classList.remove(
                    "dragover"
                );


                const files =
                    event.dataTransfer.files;


                if (files.length === 0) {
                    return;
                }


                const file =
                    files[0];


                if (!validateFile(file)) {
                    return;
                }


                try {

                    const dataTransfer =
                        new DataTransfer();

                    dataTransfer.items.add(
                        file
                    );

                    fileInput.files =
                        dataTransfer.files;

                }
                catch (error) {

                    console.log(
                        "Could not assign dropped file."
                    );
                }


                showFile(file);
            }
        );
    }


    // =========================================================
    // IMPORTANT:
    // DO NOT OPEN FILE PICKER WHEN UPLOAD BOX IS CLICKED
    //
    // Only "Browse Computer" opens the file picker.
    // =========================================================

    if (uploadBox) {

        uploadBox.addEventListener(
            "click",
            function (event) {

                const clickedBrowseButton =
                    event.target.closest(
                        ".file-select-btn"
                    );


                const clickedInput =
                    event.target.closest(
                        "#fileInput"
                    );


                if (
                    clickedBrowseButton ||
                    clickedInput
                ) {

                    return;
                }


                // Do nothing.
                //
                // This prevents clicking the upload area
                // from opening the computer file picker.

            }
        );
    }


    // =========================================================
    // UPLOAD FORM
    // =========================================================

    if (uploadForm) {

        uploadForm.addEventListener(
            "submit",
            function (event) {

                if (
                    !fileInput ||
                    !fileInput.files ||
                    fileInput.files.length === 0
                ) {

                    event.preventDefault();

                    showUploadStatus(
                        "Please select a file first.",
                        "error"
                    );

                    return;
                }


                const file =
                    fileInput.files[0];


                if (!validateFile(file)) {

                    event.preventDefault();

                    return;
                }


                // IMPORTANT:
                // Upload button does NOT open picker.

                if (uploadButton) {

                    uploadButton.disabled =
                        true;

                    uploadButton.innerHTML =
                        "⏳ Uploading...";

                    uploadButton.classList.add(
                        "uploading"
                    );
                }


                showUploadStatus(
                    "Uploading your file to the cloud...",
                    "success"
                );


                // Browser submits the form normally.
                // Flask handles S3 + RDS.

            }
        );
    }


    // =========================================================
    // FLASH MESSAGE AUTO HIDE
    // =========================================================

    const flashMessages =
        document.querySelectorAll(
            ".flash-message"
        );


    flashMessages.forEach(function (message) {

        const closeButton =
            message.querySelector(
                ".flash-close"
            );


        if (closeButton) {

            closeButton.addEventListener(
                "click",
                function () {

                    hideFlash(message);

                }
            );
        }


        setTimeout(function () {

            hideFlash(message);

        }, 3000);

    });


    function hideFlash(element) {

        if (!element) {
            return;
        }


        element.classList.add(
            "flash-hide"
        );


        setTimeout(function () {

            if (element.parentNode) {

                element.parentNode.removeChild(
                    element
                );

            }

        }, 350);

    }


    // =========================================================
    // FILTER POSITION
    // =========================================================

    if (filterForm) {

        filterForm.addEventListener(
            "submit",
            function () {

                if (!storedFiles) {
                    return;
                }


                sessionStorage.setItem(
                    "cloudDropperStoredFilesScroll",
                    window.scrollY.toString()
                );

            }
        );
    }


    // =========================================================
    // RESTORE FILTER POSITION
    // =========================================================

    const savedScroll =
        sessionStorage.getItem(
            "cloudDropperStoredFilesScroll"
        );


    if (savedScroll !== null) {

        sessionStorage.removeItem(
            "cloudDropperStoredFilesScroll"
        );


        window.requestAnimationFrame(
            function () {

                const storedSection =
                    document.getElementById(
                        "storedFiles"
                    );


                if (storedSection) {

                    const sectionTop =
                        storedSection.getBoundingClientRect().top
                        + window.scrollY;


                    // Keep user around Stored Files
                    // rather than sending them to top.

                    const target =
                        Math.max(
                            0,
                            sectionTop - 25
                        );


                    window.scrollTo({
                        top: target,
                        behavior: "instant"
                    });

                }

            }
        );
    }


});