// Autocomplete nama mengikuti jenis (pemasukan / pengeluaran) yang dipilih.
(function () {
    var radios = document.querySelectorAll('input[name="type"]');
    var nameInput = document.getElementById("name");

    var bucketLabel = document.getElementById("bucket-label");

    function sync() {
        var checked = document.querySelector('input[name="type"]:checked');
        if (checked) {
            nameInput.setAttribute("list", "names-" + checked.value);
            if (bucketLabel) {
                bucketLabel.textContent = checked.value === "income" ? "Masuk ke" : "Diambil dari";
            }
        }
    }

    radios.forEach(function (radio) {
        radio.addEventListener("change", sync);
    });
    sync();
})();
