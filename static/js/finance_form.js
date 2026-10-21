// Autocomplete nama mengikuti jenis (pemasukan / pengeluaran) yang dipilih.
(function () {
    var radios = document.querySelectorAll('input[name="type"]');
    var nameInput = document.getElementById("name");

    function sync() {
        var checked = document.querySelector('input[name="type"]:checked');
        if (checked) {
            nameInput.setAttribute("list", "names-" + checked.value);
        }
    }

    radios.forEach(function (radio) {
        radio.addEventListener("change", sync);
    });
    sync();
})();
