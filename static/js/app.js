document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.querySelector("#id_file");
    const selectedFile = document.querySelector("#selected-file");

    if (!fileInput || !selectedFile) {
        return;
    }

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];

        if (!file) {
            selectedFile.hidden = true;
            selectedFile.textContent = "";
            return;
        }

        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);

        selectedFile.textContent =
            `${file.name} · ${sizeMB} MB`;

        selectedFile.hidden = false;
    });
});