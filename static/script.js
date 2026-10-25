document.addEventListener("DOMContentLoaded", function () {

    const fileInput = document.getElementById("fileInput");
    const uploadBox = document.getElementById("uploadBox");
    const fileNamePreview = document.getElementById("fileNamePreview");
    const uploadForm = document.getElementById("uploadForm");

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


    /* =====================================================
       FILE SELECTION
       ===================================================== */

    function showFile(file) {

        if (!file) {
            return;
        }

        const fileName = file.name;

        const extension = fileName
            .split(".")
            .pop()
            .toLowerCase();


        // File type validation
        if (!allowedExtensions.includes(extension)) {

            showTemporaryMessage(
                "File type not supported. Allowed: JPG, JPEG, PNG, PDF, MP4, PPT, PPTX",
                "danger"
            );

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "No file selected";
            }

            return;
        }


        // File size validation
        if (file.size > maxSize) {

            showTemporaryMessage(
                "File size must be less than 2 MB.",
                "danger"
            );

            fileInput.value = "";

            if (fileNamePreview) {
                fileNamePreview.textContent = "No file selected";
            }

            return;
        }


        // Display selected file
        if (fileNamePreview) {

            const sizeMB =
                (file.size / 1024 / 1024).toFixed(2);

            fileNamePreview.textContent =
                "✓ " + fileName + " • " + sizeMB + " MB";
        }
    }


    /* =====================================================
       NORMAL FILE SELECTION
       ===================================================== */

    if (fileInput) {

        fileInput.addEventListener("change", function () {

            const file = this.files[0];

            showFile(file);
        });
    }


    /* =====================================================
       DRAG AND DROP
       ===================================================== */

    if (uploadBox) {

        uploadBox.addEventListener("dragover", function (event) {

            event.preventDefault();

            uploadBox.classList.add("dragover");
        });


        uploadBox.addEventListener("dragleave", function () {

            uploadBox.classList.remove("dragover");
        });


        uploadBox.addEventListener("drop", function (event) {

            event.preventDefault();

            uploadBox.classList.remove("dragover");

            const files = event.dataTransfer.files;

            if (files.length === 0) {
                return;
            }

            const file = files[0];

            try {

                const dataTransfer =
                    new DataTransfer();

                dataTransfer.items.add(file);

                fileInput.files =
                    dataTransfer.files;

            } catch (error) {

                console.log(
                    "Could not assign dropped file."
                );
            }

            showFile(file);
        });
    }


    /* =====================================================
       IMPORTANT:
       DO NOT MAKE THE WHOLE UPLOAD BOX CLICKABLE
       ===================================================== */

    // There is intentionally NO uploadBox.click()
    // handler here.

    // The browser file picker opens ONLY when the user
    // presses "Choose File".



    /* =====================================================
       PREVENT DOUBLE SUBMISSION
       ===================================================== */

    if (uploadForm) {

        uploadForm.addEventListener("submit", function (event) {

            if (!fileInput || !fileInput.files.length) {

                event.preventDefault();

                showTemporaryMessage(
                    "Please select a file first.",
                    "danger"
                );

                return;
            }


            const uploadButton =
                document.getElementById("uploadButton");


            if (uploadButton) {

                uploadButton.disabled = true;

                uploadButton.innerHTML =
                    "⏳ Uploading...";
            }

        });
    }



    /* =====================================================
       FLASH MESSAGE AUTO HIDE
       ===================================================== */

    const flashMessages =
        document.querySelectorAll(".flash-message");


    flashMessages.forEach(function (message) {

        setTimeout(function () {

            message.classList.add("message-hide");

            setTimeout(function () {

                message.remove();

            }, 400);

        }, 3000);

    });



    /* =====================================================
       TEMPORARY FRONTEND MESSAGE
       ===================================================== */

    function showTemporaryMessage(text, type) {

        let container =
            document.querySelector(".flash-container");


        if (!container) {

            container =
                document.createElement("div");

            container.className =
                "flash-container";

            document.body.appendChild(container);
        }


        const message =
            document.createElement("div");

        message.className =
            "flash-message " + type;

        message.textContent =
            text;


        container.appendChild(message);


        setTimeout(function () {

            message.classList.add("message-hide");

            setTimeout(function () {

                message.remove();

            }, 400);

        }, 3000);
    }



    /* =====================================================
       PRESERVE SCROLL POSITION AFTER FILTER
       ===================================================== */

    const filterForm =
        document.querySelector(".search-bar");


    if (filterForm) {

        filterForm.addEventListener("submit", function () {

            sessionStorage.setItem(
                "cloudDropperScrollPosition",
                window.scrollY
            );

        });
    }


    const savedScrollPosition =
        sessionStorage.getItem(
            "cloudDropperScrollPosition"
        );


    if (savedScrollPosition !== null) {

        sessionStorage.removeItem(
            "cloudDropperScrollPosition"
        );


        window.requestAnimationFrame(function () {

            window.scrollTo(
                0,
                parseInt(savedScrollPosition, 10)
            );

        });
    }

});