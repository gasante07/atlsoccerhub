// Referral Manager - Handles referral codes, links, sharing, and stats
class ReferralManager {
  constructor() {
    this.apiEndpoint = "/api/referral";
    this.referralCode = null;
    this.referrerInfo = null;
    this.init();
  }

  init() {
    // Detect referral code from URL
    this.detectReferralFromURL();
    
    // Store referral code for form submission
    if (this.referralCode) {
      this.storeReferralCode(this.referralCode);
      this.loadReferrerInfo();
    }
  }

  detectReferralFromURL() {
    const params = new URLSearchParams(window.location.search);
    const refCode = params.get("ref");
    
    if (refCode) {
      this.referralCode = refCode.trim().toUpperCase();
      return true;
    }
    
    return false;
  }

  storeReferralCode(code) {
    try {
      localStorage.setItem("soccer_hub_referral_code", code);
    } catch (e) {
      console.warn("Failed to store referral code:", e);
    }
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

  async loadReferrerInfo() {
    if (!this.referralCode) return;

    try {
      const response = await fetch(`${this.apiEndpoint}/code/${encodeURIComponent(this.referralCode)}`);
      const data = await response.json();
      
      if (data.ok && data.valid) {
        this.referrerInfo = {
          email: data.referrer_email,
          name: data.referrer_name
        };
        this.showReferrerMessage();
      }
    } catch (e) {
      console.warn("Failed to load referrer info:", e);
    }
  }

  showReferrerMessage() {
    if (!this.referrerInfo) return;

    // Create and show referrer message
    const messageContainer = document.createElement("div");
    messageContainer.className = "referral-message";
    messageContainer.setAttribute("data-referral-message", "");
    messageContainer.innerHTML = `
      <p class="referral-message__text">
        You were referred by <strong>${this.escapeHtml(this.referrerInfo.name)}</strong>!
      </p>
    `;

    // Insert before form or hero section
    const form = document.querySelector("#notify-form");
    const hero = document.querySelector(".hero");
    const target = form || hero;
    
    if (target && target.parentNode) {
      target.parentNode.insertBefore(messageContainer, target);
    }
  }

  async generateCode(email) {
    try {
      const response = await fetch(`${this.apiEndpoint}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();
      
      if (data.ok) {
        this.referralCode = data.referral_code;
        return { success: true, code: data.referral_code };
      } else {
        return { success: false, error: data.error || "Failed to generate code" };
      }
    } catch (e) {
      console.error("Error generating referral code:", e);
      return { success: false, error: e.message };
    }
  }

  async getStats(email) {
    try {
      const response = await fetch(`${this.apiEndpoint}/stats?email=${encodeURIComponent(email)}`);
      const data = await response.json();
      
      if (data.ok) {
        return {
          success: true,
          hasCode: data.has_code,
          referralCode: data.referral_code,
          referralCount: data.referral_count || 0,
          badges: data.badges || [],
          rank: data.rank
        };
      } else {
        return { success: false, error: data.error || "Failed to get stats" };
      }
    } catch (e) {
      console.error("Error getting referral stats:", e);
      return { success: false, error: e.message };
    }
  }

  async getLeaderboard(limit = 10) {
    try {
      const response = await fetch(`${this.apiEndpoint}/leaderboard?limit=${limit}`);
      const data = await response.json();
      
      if (data.ok) {
        return { success: true, leaderboard: data.leaderboard || [] };
      } else {
        return { success: false, error: data.error || "Failed to get leaderboard" };
      }
    } catch (e) {
      console.error("Error getting leaderboard:", e);
      return { success: false, error: e.message };
    }
  }

  generateReferralLink(code, baseUrl = null) {
    if (!code) return null;
    
    const url = baseUrl || window.location.origin + window.location.pathname;
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}ref=${code}`;
  }

  async copyToClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return { success: true };
      } else {
        // Fallback for older browsers
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        const success = document.execCommand("copy");
        document.body.removeChild(textarea);
        return { success: success };
      }
    } catch (e) {
      console.error("Failed to copy to clipboard:", e);
      return { success: false, error: e.message };
    }
  }

  async shareLink(link, title = null, text = null) {
    const site = (typeof document !== "undefined" && document.body?.getAttribute("data-site-name")) || "Atlanta Soccer Hub";
    const hub = (typeof document !== "undefined" && document.body?.getAttribute("data-hub-marketing-name")) || "Metro Atlanta";
    title = title || `Join ${site}`;
    text = text || `Check out ${site} - find, organize, and play pickup soccer in ${hub}!`;
    if (navigator.share) {
      try {
        await navigator.share({
          title: title,
          text: text,
          url: link
        });
        return { success: true, method: "native" };
      } catch (e) {
        if (e.name !== "AbortError") {
          console.error("Share failed:", e);
        }
        return { success: false, error: e.message };
      }
    } else {
      // Fallback to clipboard
      const result = await this.copyToClipboard(link);
      if (result.success) {
        return { success: true, method: "clipboard" };
      }
      return { success: false, error: "Share not supported" };
    }
  }

  getBadgeLabel(badgeType) {
    const badges = {
      "first_referral": "First Referral",
      "five_referrals": "Community Builder",
      "ten_referrals": "Growth Champion",
      "twenty_five_referrals": "Viral Leader",
      "fifty_referrals": "Legend"
    };
    return badges[badgeType] || badgeType;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  formatReferralCode(code) {
    // Format code for display (REF-XXXX-XXXX)
    if (!code) return "";
    return code.toUpperCase().replace(/(.{3})(.{4})(.{4})/, "$1-$2-$3");
  }
}

// Make available globally
window.ReferralManager = ReferralManager;

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = ReferralManager;
}
