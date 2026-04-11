(function () {
  if (window.processedgePosnextOverrideInitialized) {
    return;
  }
  window.processedgePosnextOverrideInitialized = true;

  const STATE = {
    settings: null,
    postingDate: null,
    observer: null,
  };

  function isPOSPage() {
    return window.location.pathname === "/pos" || window.location.pathname.startsWith("/pos/");
  }

  function getToday() {
    return new Date().toISOString().slice(0, 10);
  }

  function callAPI(method, args) {
    return new Promise((resolve, reject) => {
      if (!window.frappe || !window.frappe.call) {
        reject(new Error("frappe.call is unavailable"));
        return;
      }

      window.frappe.call({
        method,
        args: args || {},
        callback: (r) => resolve(r.message || r),
        error: reject,
      });
    });
  }

  async function loadSettings() {
    try {
      const data = await callAPI("processedge_posnext_override.api.get_pos_override_settings");
      STATE.settings = data || {};
      STATE.postingDate = data && data.posting_date ? data.posting_date : getToday();
    } catch (error) {
      console.warn("ProcessEdge POSNext Override: failed to load settings", error);
      STATE.settings = {
        allow_editable_selling_price: 0,
        allow_editing_posting_date: 0,
      };
      STATE.postingDate = getToday();
    }
  }

  function parseBody(body) {
    if (!body) return null;

    if (typeof body === "string") {
      return new URLSearchParams(body);
    }

    if (body instanceof URLSearchParams) {
      return new URLSearchParams(body.toString());
    }

    if (body instanceof FormData) {
      const params = new URLSearchParams();
      body.forEach((value, key) => params.set(key, value));
      return params;
    }

    return null;
  }

  function writeInvoiceDateFields(payload) {
    if (!payload || !STATE.settings || !STATE.settings.allow_editing_posting_date || !STATE.postingDate) {
      return payload;
    }

    payload.posting_date = STATE.postingDate;
    payload.transaction_date = STATE.postingDate;
    return payload;
  }

  function patchRequestPayload(url, init) {
    const params = parseBody(init && init.body);
    if (!params) {
      return init;
    }

    if (url.includes("pos_next.api.invoices.update_invoice")) {
      const raw = params.get("data");
      if (raw) {
        const data = JSON.parse(raw);
        writeInvoiceDateFields(data);
        params.set("data", JSON.stringify(data));
      }
    }

    if (url.includes("pos_next.api.invoices.submit_invoice")) {
      const invoiceRaw = params.get("invoice");
      if (invoiceRaw) {
        const invoice = JSON.parse(invoiceRaw);
        writeInvoiceDateFields(invoice);
        params.set("invoice", JSON.stringify(invoice));
      }
    }

    if (url.includes("pos_next.api.invoices.apply_offers")) {
      const invoiceDataRaw = params.get("invoice_data");
      if (invoiceDataRaw) {
        const invoiceData = JSON.parse(invoiceDataRaw);
        writeInvoiceDateFields(invoiceData);
        params.set("invoice_data", JSON.stringify(invoiceData));
      }
    }

    const nextInit = Object.assign({}, init || {});
    nextInit.body = params.toString();
    nextInit.headers = Object.assign({}, (init && init.headers) || {});
    if (!nextInit.headers["Content-Type"] && !nextInit.headers["content-type"]) {
      nextInit.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    }
    return nextInit;
  }

  function patchFetch() {
    if (!window.fetch || window.fetch.__processedgePosnextPatched) {
      return;
    }

    const originalFetch = window.fetch.bind(window);
    const patched = function (input, init) {
      const url = typeof input === "string" ? input : input && input.url;
      if (url && isPOSPage()) {
        init = patchRequestPayload(url, init);
      }
      return originalFetch(input, init);
    };

    patched.__processedgePosnextPatched = true;
    window.fetch = patched;
  }

  function createPostingDateField(dialogBody) {
    if (!dialogBody || dialogBody.querySelector("[data-processedge-posting-date]")) {
      return;
    }

    const target = dialogBody.querySelector(".bg-orange-50, .lg\\:col-span-2, .grid");
    if (!target || !target.parentNode) {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.setAttribute("data-processedge-posting-date", "1");
    wrapper.className = "bg-blue-50 border border-blue-200 rounded-lg p-2";
    wrapper.innerHTML = [
      '<div class="flex items-center gap-2">',
      '<svg class="w-4 h-4 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>',
      "</svg>",
      '<label class="text-xs font-medium text-blue-700 flex-shrink-0">Posting Date</label>',
      `<input type="date" value="${STATE.postingDate || getToday()}" class="flex-1 h-8 border border-blue-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" />`,
      "</div>",
      "</div>",
    ].join("");

    const input = wrapper.querySelector("input");
    if (input) {
      input.addEventListener("change", function (event) {
        STATE.postingDate = event.target.value || getToday();
      });
    }

    target.parentNode.insertBefore(wrapper, target);
  }

  function createPersistentPostingDateField(container) {
    if (!container || container.querySelector("[data-processedge-posting-date-global]")) {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.setAttribute("data-processedge-posting-date-global", "1");
    wrapper.className = "processedge-posting-date-global";
    wrapper.style.cssText = [
      "display:flex",
      "align-items:center",
      "gap:8px",
      "padding:8px 12px",
      "margin:8px 0",
      "border:1px solid #bfdbfe",
      "border-radius:12px",
      "background:#eff6ff",
      "font-size:14px",
      "width:fit-content",
      "max-width:100%",
    ].join(";");
    wrapper.innerHTML = [
      '<label style="font-weight:600;color:#1d4ed8;white-space:nowrap;">Posting Date</label>',
      `<input type="date" value="${STATE.postingDate || getToday()}" style="height:36px;padding:0 10px;border:1px solid #93c5fd;border-radius:10px;background:#fff;min-width:170px;" />`,
    ].join("");

    const input = wrapper.querySelector("input");
    if (input) {
      input.addEventListener("change", function (event) {
        STATE.postingDate = event.target.value || getToday();
      });
    }

    container.prepend(wrapper);
  }

  function createFloatingPostingDateField() {
    if (document.querySelector("[data-processedge-posting-date-floating]")) {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.setAttribute("data-processedge-posting-date-floating", "1");
    wrapper.style.cssText = [
      "position:fixed",
      "right:24px",
      "bottom:96px",
      "z-index:9999",
      "display:flex",
      "align-items:center",
      "gap:8px",
      "padding:10px 12px",
      "border:1px solid #bfdbfe",
      "border-radius:14px",
      "background:#eff6ff",
      "box-shadow:0 10px 30px rgba(15, 23, 42, 0.12)",
      "font-size:14px",
      "max-width:calc(100vw - 48px)",
    ].join(";");
    wrapper.innerHTML = [
      '<label style="font-weight:600;color:#1d4ed8;white-space:nowrap;">Posting Date</label>',
      `<input type="date" value="${STATE.postingDate || getToday()}" style="height:36px;padding:0 10px;border:1px solid #93c5fd;border-radius:10px;background:#fff;min-width:170px;" />`,
    ].join("");

    const input = wrapper.querySelector("input");
    if (input) {
      input.addEventListener("change", function (event) {
        STATE.postingDate = event.target.value || getToday();
      });
    }

    document.body.appendChild(wrapper);
  }

  function injectPostingDateIntoPage() {
    if (!STATE.settings || !STATE.settings.allow_editing_posting_date) {
      return;
    }

    const candidates = [
      "[data-v-app] main",
      "#app main",
      ".layout-main-section",
      ".page-content",
      "main",
    ];

    for (const selector of candidates) {
      const container = document.querySelector(selector);
      if (container) {
        createPersistentPostingDateField(container);
        createFloatingPostingDateField();
        return;
      }
    }

    createFloatingPostingDateField();
  }

  function unlockRateInputs() {
    if (!STATE.settings || !STATE.settings.allow_editable_selling_price) {
      return;
    }

    const dialogs = Array.from(document.querySelectorAll("[role='dialog'], .dialog-content, .frappe-dialog, .z-dialog-content"));
    dialogs.forEach((dialog) => {
      const text = dialog.textContent || "";
      if (!text.includes("Edit Item Details")) {
        return;
      }

      const rateLabels = Array.from(dialog.querySelectorAll("label")).filter((label) =>
        (label.textContent || "").trim() === "Rate"
      );

      rateLabels.forEach((label) => {
        const section = label.parentElement;
        if (!section) {
          return;
        }

        const input = section.querySelector("input[type='number']");
        if (!input) {
          return;
        }

        input.readOnly = false;
        input.removeAttribute("readonly");
        input.disabled = false;
        input.removeAttribute("disabled");
        input.classList.remove("cursor-not-allowed", "bg-gray-50");
        input.classList.add("bg-white");
        input.title = "Editable by ProcessEdge POSNext Override";

        const warning = section.querySelector("p");
        if (warning && /locked|disabled/i.test(warning.textContent || "")) {
          warning.style.display = "none";
        }
      });
    });
  }

  function patchUI() {
    unlockRateInputs();

    if (!STATE.settings || !STATE.settings.allow_editing_posting_date) {
      return;
    }

    injectPostingDateIntoPage();

    const dialogTitles = Array.from(document.querySelectorAll("[role='dialog'], .dialog-content, .frappe-dialog, .z-dialog-content"));
    dialogTitles.forEach((dialog) => {
      if (!dialog || dialog.querySelector("[data-processedge-posting-date]")) {
        return;
      }

      const text = dialog.textContent || "";
      if (
        text.includes("Complete Payment") ||
        text.includes("Complete Sales Order") ||
        text.includes("Payment") ||
        text.includes("Amount Paid")
      ) {
        createPostingDateField(dialog);
      }
    });
  }

  function startObserver() {
    if (STATE.observer) {
      STATE.observer.disconnect();
    }

    STATE.observer = new MutationObserver(function () {
      patchUI();
    });

    STATE.observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  async function boot() {
    if (!isPOSPage()) {
      return;
    }

    await loadSettings();
    patchFetch();
    patchUI();
    startObserver();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
