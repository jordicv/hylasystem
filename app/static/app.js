(function () {
  var toggle = document.getElementById("sidebarToggle");
  var backdrop = document.getElementById("sidebarBackdrop");

  if (!toggle) {
    attachInlineForms();
    return;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
  }

  function openSidebar() {
    document.body.classList.add("sidebar-open");
  }

  toggle.addEventListener("click", function () {
    if (document.body.classList.contains("sidebar-open")) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  if (backdrop) {
    backdrop.addEventListener("click", closeSidebar);
  }

  attachInlineForms();

  function attachInlineForms() {
    var selects = document.querySelectorAll(".inline-form select");
    selects.forEach(function (select) {
      select.addEventListener("change", function (event) {
        var form = event.target.form;
        if (!form) {
          return;
        }
        var formData = new FormData(form);
        fetch(form.action, {
          method: "POST",
          body: formData,
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest"
          }
        });
      });
    });
  }
})();
