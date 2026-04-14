// Storage abstraction layer for lead submissions (leads endpoint e.g. Google Sheets, or API or localStorage)
class StorageManager {
  constructor(mode = "python", leadsEndpoint = "") {
    this.mode = mode;
    this.apiEndpoint = "/api/notify";
    this.leadsEndpoint = (leadsEndpoint || "").trim();
  }

  async submit(data) {
    if (this.leadsEndpoint) {
      return this.submitToLeads(data);
    }
    if (this.mode === "python") {
      return this.submitToAPI(data);
    }
    return this.submitToLocalStorage(data);
  }

  async submitToLeads(data) {
    if (this._leadsSubmitting) {
      return { success: false, error: "Submission already in progress." };
    }
    this._leadsSubmitting = true;

    return new Promise((resolve) => {
      let settled = false;
      const settle = (result) => {
        if (settled) return;
        settled = true;
        this._leadsSubmitting = false;
        iframe.onload = null;
        iframe.onerror = null;
        setTimeout(() => {
          if (form.parentNode) form.parentNode.removeChild(form);
          if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
        }, 2000);
        resolve(result);
      };

      let iframe, form;
      try {
        const iframeName = "leads_iframe_" + Date.now();
        iframe = document.createElement("iframe");
        iframe.name = iframeName;
        iframe.style.display = "none";
        document.body.appendChild(iframe);

        form = document.createElement("form");
        form.method = "POST";
        form.action = this.leadsEndpoint;
        form.target = iframeName;
        form.style.display = "none";

        for (const [key, value] of Object.entries(data)) {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = key;
          input.value = typeof value === "object" ? JSON.stringify(value) : String(value);
          form.appendChild(input);
        }

        document.body.appendChild(form);

        iframe.onload = () => settle({ success: true, data: {} });
        iframe.onerror = () => settle({ success: false, error: "Unable to connect. Please check your connection and try again." });

        form.submit();

        setTimeout(() => settle({ success: true, data: {} }), 10000);
      } catch (error) {
        console.error("Leads submission error:", error);
        this._leadsSubmitting = false;
        resolve({ success: false, error: error.message });
      }
    });
  }

  async submitToAPI(data) {
    try {
      const response = await fetch(this.apiEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
      });

      // Clone response to avoid "body stream already read" error
      const responseClone = response.clone();
      
      let result;
      try {
        result = await response.json();
      } catch (jsonError) {
        // If response is not JSON, get text from cloned response
        const text = await responseClone.text();
        console.error("Non-JSON response:", text);
        throw new Error(`Server error: ${response.status} ${response.statusText}`);
      }
      
      if (!response.ok) {
        const errorMsg = result?.error || `Server error: ${response.status} ${response.statusText}`;
        console.error("API error response:", result);
        throw new Error(errorMsg);
      }

      return { success: true, data: result };
    } catch (error) {
      console.error("API submission error:", error);
      
      // Provide more helpful error messages
      let errorMessage = error.message;
      if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
        errorMessage = "Unable to connect to server. Please check your internet connection and try again.";
      } else if (error.message.includes("405")) {
        errorMessage = "API endpoint not available. Please ensure the server is running with API routes enabled.";
      } else if (error.message.includes("429")) {
        errorMessage = "Too many requests. Please wait a moment and try again.";
      } else if (error.message.includes("500")) {
        errorMessage = "Server error. Please try again later.";
      }
      
      return { success: false, error: errorMessage, originalError: error.message };
    }
  }

  submitToLocalStorage(data) {
    try {
      const submissions = JSON.parse(localStorage.getItem("soccer_hub_submissions") || "[]");
      submissions.push({
        ...data,
        submittedAt: new Date().toISOString()
      });
      localStorage.setItem("soccer_hub_submissions", JSON.stringify(submissions));
      return { success: true, data: { ok: true } };
    } catch (error) {
      console.error("LocalStorage submission error:", error);
      return { success: false, error: error.message };
    }
  }

  hasSubmitted() {
    return localStorage.getItem("soccer_hub_submitted") === "true";
  }

  markAsSubmitted() {
    localStorage.setItem("soccer_hub_submitted", "true");
  }

  hasModalShownThisSession() {
    return sessionStorage.getItem("soccer_hub_modal_shown") === "true";
  }

  markModalAsShown() {
    sessionStorage.setItem("soccer_hub_modal_shown", "true");
  }

  getStoredReferralCode() {
    try {
      return localStorage.getItem("soccer_hub_referral_code");
    } catch (e) {
      return null;
    }
  }

  clearStoredReferralCode() {
    try {
      localStorage.removeItem("soccer_hub_referral_code");
    } catch (e) {
      // Ignore
    }
  }
}

// Make available globally
window.StorageManager = StorageManager;

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = StorageManager;
}

