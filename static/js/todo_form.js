// Tampilkan field sesuai tipe todo: sekali -> deadline, hari tertentu -> pilihan hari.
(function () {
    var select = document.getElementById("repeat_type");
    var onceBox = document.getElementById("once-fields");
    var weeklyBox = document.getElementById("weekly-fields");

    function sync() {
        onceBox.hidden = select.value !== "once";
        weeklyBox.hidden = select.value !== "weekly";
    }

    select.addEventListener("change", sync);
    sync();
})();
