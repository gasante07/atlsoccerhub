// Main JavaScript for UI behavior, form management, and interactions
(function() {
  "use strict";

  // Modal Manager
  class ModalManager {
    constructor(modalSelector) {
      this.modal = document.querySelector(modalSelector);
      this.backdrop = this.modal?.querySelector("[data-modal-close]");
      this.closeButtons = this.modal?.querySelectorAll("[data-modal-close]");
      this.isOpen = false;
      this.init();
    }

    init() {
      if (!this.modal) return;

      // Close buttons
      this.closeButtons?.forEach(btn => {
        btn.addEventListener("click", () => this.close());
      });

      // Escape key
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && this.isOpen) {
          this.close();
        }
      });

      // Focus trap
      this.setupFocusTrap();
    }

    updateModalContent(context) {
      if (!this.modal) return;
      
      const modalTitle = this.modal.querySelector("#modal-title");
      const modalDescription = this.modal.querySelector("[data-modal-description]");
      const modalMicrocopy = this.modal.querySelector("[data-modal-microcopy]");
      const formSubmit = this.modal.querySelector("[data-form-submit-text]");
      
      if (context === "organisers") {
        if (modalTitle) modalTitle.textContent = "Get Organizer Updates";
        if (modalDescription) {
          modalDescription.textContent = "Fill spots faster, grow recurring games, and connect with players who actually show up. We'll notify you when organizer tools launch.";
        }
        if (modalMicrocopy) {
          modalMicrocopy.textContent = "We'll only email useful organizer updates. Unsubscribe anytime.";
          modalMicrocopy.style.display = "block";
        }
        if (formSubmit) formSubmit.textContent = "Get organizer updates";
      } else {
        // Default to players context
        if (modalTitle) modalTitle.textContent = "Get Local Game Invites";
        if (modalDescription) {
          const siteName = document.body.getAttribute("data-site-name") || "Atlanta Soccer Hub";
          modalDescription.textContent = `Join ${siteName} to get local game updates, weekly runs, and last-minute spots. We'll notify you when new games go live near you.`;
        }
        if (modalMicrocopy) {
          modalMicrocopy.textContent = "No spam. Just local soccer updates. Unsubscribe anytime.";
          modalMicrocopy.style.display = "block";
        }
        if (formSubmit) formSubmit.textContent = "Get local game invites";
      }
    }

    open(context, options) {
      if (!this.modal) return;
      
      this._opener = options?.trigger ?? null;

      // Update modal content based on context
      if (context) {
        this.updateModalContent(context);
      } else {
        // Try to get context from body attribute or hero tabs
        const heroContext = document.body.getAttribute("data-hero-context") || "players";
        this.updateModalContent(heroContext);
      }
      
      this.modal.setAttribute("aria-hidden", "false");
      this.isOpen = true;
      document.body.style.overflow = "hidden";

      if (typeof window.trackEvent === "function") {
        window.trackEvent("modal_open", { context: context || document.body.getAttribute("data-hero-context") || "players" });
      }
      
      // Focus first input
      const firstInput = this.modal.querySelector("input, textarea, select");
      if (firstInput) {
        setTimeout(() => firstInput.focus(), 100);
      }
    }

    close() {
      if (!this.modal) return;
      
      this.modal.setAttribute("aria-hidden", "true");
      this.isOpen = false;
      document.body.style.overflow = "";

      // Move focus out of modal so it is not hidden from assistive technology
      const opener = this._opener;
      this._opener = null;
      if (opener && typeof opener.focus === "function" && document.body.contains(opener)) {
        opener.focus();
      } else {
        const fallback = document.querySelector("[data-form-trigger]") || document.body;
        if (fallback && typeof fallback.focus === "function") {
          fallback.focus();
        }
      }
    }

    setupFocusTrap() {
      const focusableElements = this.modal.querySelectorAll(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      this.modal.addEventListener("keydown", (e) => {
        if (e.key !== "Tab") return;
        
        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      });
    }
  }

  // Form Manager
  class FormManager {
    constructor(formSelector, storageManager) {
      this.form = document.querySelector(formSelector);
      this.storageManager = storageManager;
      this.expandedSection = this.form?.querySelector("[data-form-expanded]");
      this.expandToggle = this.form?.querySelector("[data-form-expand-toggle]");
      this.init();
    }

    init() {
      if (!this.form) return;

      // Form submission
      this.form.addEventListener("submit", (e) => this.handleSubmit(e));

      // Expand toggle
      this.expandToggle?.addEventListener("click", () => this.toggleExpanded());

      // Field validation
      this.setupValidation();
    }

    setupValidation() {
      const fields = this.form.querySelectorAll("input[required], select[required], textarea[required]");
      fields.forEach(field => {
        field.addEventListener("blur", () => this.validateField(field));
        field.addEventListener("input", () => this.clearError(field));
      });
    }

    validateField(field) {
      const errorElement = this.form.querySelector(`[data-field-error="${field.name}"]`);
      
      if (!field.validity.valid) {
        this.showError(field, this.getErrorMessage(field));
        return false;
      } else {
        this.clearError(field);
        return true;
      }
    }

    getErrorMessage(field) {
      if (field.validity.valueMissing) {
        return "This field is required";
      }
      if (field.validity.typeMismatch) {
        if (field.type === "email") return "Please enter a valid email address";
      }
      return "Please check this field";
    }

    showError(field, message) {
      field.classList.add("form__input--error");
      const errorElement = this.form.querySelector(`[data-field-error="${field.name}"]`);
      if (errorElement) {
        errorElement.textContent = message;
      }
    }

    clearError(field) {
      field.classList.remove("form__input--error");
      const errorElement = this.form.querySelector(`[data-field-error="${field.name}"]`);
      if (errorElement) {
        errorElement.textContent = "";
      }
    }

    toggleExpanded() {
      if (!this.expandedSection || !this.expandToggle) return;
      
      const isExpanded = this.expandedSection.style.display !== "none";
      this.expandedSection.style.display = isExpanded ? "none" : "block";
      this.expandToggle.textContent = isExpanded ? "More options" : "Fewer options";
    }

    async handleSubmit(e) {
      e.preventDefault();

      // Validate all required fields
      const requiredFields = this.form.querySelectorAll("[required]");
      let isValid = true;
      requiredFields.forEach(field => {
        if (!this.validateField(field)) {
          isValid = false;
        }
      });

      if (!isValid) return;

      // Check honeypot
      const honeypot = this.form.querySelector('input[name="website"]');
      if (honeypot && honeypot.value) {
        console.warn("Honeypot field filled - potential spam");
        return;
      }

      // Collect form data
      const formData = new FormData(this.form);
      
      // Get stored referral code if available
      const storedReferralCode = this.storageManager.getStoredReferralCode();
      
      const data = {
        email: formData.get("email"),
        city: formData.get("city"),
        name: formData.get("name") || "",
        phone: formData.get("phone") || "",
        skill_level: formData.get("skill_level") || "",
        organizer_interest: formData.get("organizer_interest") ? "yes" : "no",
        preferred_times: formData.get("preferred_times") || "",
        consent: !!formData.get("consent"),
        page_url: window.location.href,
        utm_json: JSON.stringify(this.getUTMParams()),
        referral_code: storedReferralCode || null
      };

      // Submit
      const submitButton = this.form.querySelector('button[type="submit"]');
      const originalText = submitButton.textContent;
      submitButton.disabled = true;
      submitButton.textContent = "Submitting...";

      const result = await this.storageManager.submit(data);

      if (result.success) {
        if (typeof window.trackEvent === "function") {
          window.trackEvent("form_submit_success", {
            context: document.body.getAttribute("data-hero-context") || "players",
            organizer_interest: data.organizer_interest === "yes"
          });
        }
        // Get referral code from response if available
        const referralCode = result.data?.referral_code || null;
        
        this.showSuccess(data.organizer_interest === "yes", data.email, referralCode);
        this.storageManager.markAsSubmitted();
        
        // Clear stored referral code after successful submission
        if (storedReferralCode) {
          this.storageManager.clearStoredReferralCode();
        }
        
        this.form.reset();
      } else {
        const errorMsg = result.error || "There was an error submitting your form. Please try again.";
        if (typeof window.trackEvent === "function") {
          window.trackEvent("form_submit_error", { error: errorMsg });
        }
        console.error("Form submission failed:", result);
        
        // Try to show error in form if error element exists
        const errorElement = this.form.querySelector("[data-form-error]");
        if (errorElement) {
          errorElement.textContent = errorMsg;
          errorElement.style.display = "block";
          errorElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } else {
          alert(errorMsg);
        }
        
        submitButton.disabled = false;
        submitButton.textContent = originalText;
      }
    }

    async showSuccess(isOrganizer, email, referralCode) {
      const successSection = this.form.querySelector("[data-form-success]");
      const successMessage = this.form.querySelector("[data-success-message]");
      const organizerMessage = this.form.querySelector("[data-organizer-message]");
      const referralDashboard = this.form.querySelector("[data-referral-dashboard]");
      const formFields = this.form.querySelectorAll(".form__field, .form__expand-link, .form__submit");

      // Hide form fields
      formFields.forEach(field => {
        field.style.display = "none";
      });

      // Show success message
      if (successSection) {
        successSection.style.display = "block";
        
        // Update success message based on context
        const context = document.body.getAttribute("data-hero-context") || "players";
        if (successMessage) {
          if (context === "organisers" || isOrganizer) {
            successMessage.textContent = "Thanks for signing up! We'll notify you when organizer tools launch and send you updates on building your soccer community.";
          } else {
            successMessage.textContent = (() => {
              const siteName = document.body.getAttribute("data-site-name") || "Atlanta Soccer Hub";
              return `Welcome to ${siteName}! You're now part of our community. We'll notify you when new games go live near you.`;
            })();
          }
        }
        
        if (isOrganizer && organizerMessage) {
          organizerMessage.style.display = "block";
        }
      }

      // Show referral dashboard if available
      if (referralDashboard && email) {
        await this.showReferralDashboard(email, referralCode, referralDashboard);
      }

      // Scroll to success message
      successSection?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async showReferralDashboard(email, referralCode, container) {
      // Initialize referral manager if not already available
      if (!window.referralManager) {
        window.referralManager = new ReferralManager();
      }

      const referralManager = window.referralManager;

      // Get or generate referral code
      let code = referralCode;
      if (!code) {
        const codeResult = await referralManager.generateCode(email);
        if (codeResult.success) {
          code = codeResult.code;
        }
      }

      if (!code) {
        container.style.display = "none";
        return;
      }

      // Get stats
      const statsResult = await referralManager.getStats(email);
      
      if (statsResult.success && statsResult.hasCode) {
        container.style.display = "block";
        
        // Update referral code display
        const codeDisplay = container.querySelector("[data-referral-code]");
        if (codeDisplay) {
          codeDisplay.textContent = statsResult.referralCode;
        }

        // Update referral link
        const linkInput = container.querySelector("[data-referral-link]");
        if (linkInput) {
          linkInput.value = referralManager.generateReferralLink(statsResult.referralCode);
        }

        // Update stats
        const countDisplay = container.querySelector("[data-referral-count]");
        if (countDisplay) {
          countDisplay.textContent = statsResult.referralCount || 0;
        }

        const rankDisplay = container.querySelector("[data-referral-rank]");
        if (rankDisplay && statsResult.rank) {
          rankDisplay.textContent = `#${statsResult.rank}`;
          rankDisplay.style.display = "inline";
        }

        // Update badges
        const badgesContainer = container.querySelector("[data-referral-badges]");
        if (badgesContainer && statsResult.badges && statsResult.badges.length > 0) {
          badgesContainer.innerHTML = statsResult.badges.map(badge => 
            `<span class="badge badge--${badge.type}">${referralManager.getBadgeLabel(badge.type)}</span>`
          ).join("");
          badgesContainer.style.display = "flex";
        }

        // Setup copy button
        const copyButton = container.querySelector("[data-referral-copy]");
        if (copyButton) {
          copyButton.addEventListener("click", async () => {
            const link = linkInput?.value || referralManager.generateReferralLink(statsResult.referralCode);
            const result = await referralManager.copyToClipboard(link);
            if (result.success) {
              const originalText = copyButton.textContent;
              copyButton.textContent = "Copied!";
              copyButton.disabled = true;
              setTimeout(() => {
                copyButton.textContent = originalText;
                copyButton.disabled = false;
              }, 2000);
            }
          });
        }

        // Setup share button
        const shareButton = container.querySelector("[data-referral-share]");
        if (shareButton) {
          shareButton.addEventListener("click", async () => {
            const link = linkInput?.value || referralManager.generateReferralLink(statsResult.referralCode);
            await referralManager.shareLink(link);
          });
        }
      } else {
        container.style.display = "none";
      }
    }

    getUTMParams() {
      const params = new URLSearchParams(window.location.search);
      const utm = {};
      params.forEach((value, key) => {
        if (key.startsWith("utm_")) {
          utm[key] = value;
        }
      });
      return utm;
    }
  }

  // Hero Tabs Manager
  class HeroTabsManager {
    constructor() {
      this.tabsContainer = document.querySelector("[data-hero-tabs]");
      this.tabs = this.tabsContainer?.querySelectorAll("[data-hero-tab]");
      this.panels = document.querySelectorAll("[data-hero-panel]");
      this.currentContext = "players"; // Default context
      this.init();
    }

    init() {
      if (!this.tabsContainer || !this.tabs || !this.panels) return;

      this.tabs.forEach(tab => {
        tab.addEventListener("click", (e) => {
          e.preventDefault();
          const targetTab = tab.getAttribute("data-hero-tab");
          this.switchTab(targetTab);
        });
      });

      // Set organizer interest checkbox when switching tabs
      this.tabs.forEach(tab => {
        tab.addEventListener("click", () => {
          const targetTab = tab.getAttribute("data-hero-tab");
          this.currentContext = targetTab;
          const organizerCheckbox = document.querySelector('input[name="organizer_interest"]');
          if (organizerCheckbox && targetTab === "organisers") {
            organizerCheckbox.checked = true;
          } else if (organizerCheckbox && targetTab === "players") {
            organizerCheckbox.checked = false;
          }
        });
      });

      // Track which hero CTA was clicked
      const heroCtas = document.querySelectorAll("[data-hero-cta]");
      heroCtas.forEach(cta => {
        cta.addEventListener("click", (e) => {
          const context = cta.getAttribute("data-hero-cta");
          this.currentContext = context;
          // Store context for modal to use
          document.body.setAttribute("data-hero-context", context);
        });
      });
    }

    switchTab(targetTab) {
      this.currentContext = targetTab;
      document.body.setAttribute("data-hero-context", targetTab);
      
      // Update tabs
      this.tabs.forEach(tab => {
        const tabName = tab.getAttribute("data-hero-tab");
        if (tabName === targetTab) {
          tab.classList.add("hero__tab--active");
          tab.setAttribute("aria-selected", "true");
        } else {
          tab.classList.remove("hero__tab--active");
          tab.setAttribute("aria-selected", "false");
        }
      });

      // Update panels
      this.panels.forEach(panel => {
        const panelName = panel.getAttribute("data-hero-panel");
        if (panelName === targetTab) {
          panel.classList.add("hero__panel--active");
        } else {
          panel.classList.remove("hero__panel--active");
        }
      });
    }

    getCurrentContext() {
      return this.currentContext || document.body.getAttribute("data-hero-context") || "players";
    }
  }

  // Navigation Manager
  class NavigationManager {
    constructor() {
      this.menuToggle = document.querySelector("[data-menu-toggle]");
      this.menuClose = document.querySelector("[data-menu-close]");
      this.navMenu = document.querySelector("[data-nav-menu]");
      this.navLinks = document.querySelectorAll(".nav__link");
      this.init();
    }

    init() {
      this.menuToggle?.addEventListener("click", () => this.toggleMenu());
      this.menuClose?.addEventListener("click", () => this.closeMenu());
      
      // Close menu when clicking nav links on mobile
      this.navLinks.forEach(link => {
        link.addEventListener("click", () => {
          if (window.innerWidth <= 767) {
            this.closeMenu();
          }
        });
      });

      // Close menu when clicking backdrop (outside menu)
      document.addEventListener("click", (e) => {
        if (window.innerWidth <= 767 && 
            this.navMenu && 
            this.navMenu.getAttribute("data-open") === "true" &&
            !this.navMenu.contains(e.target) &&
            !this.menuToggle?.contains(e.target)) {
          this.closeMenu();
        }
      });
    }

    toggleMenu() {
      if (!this.navMenu) return;
      const isOpen = this.navMenu.getAttribute("data-open") === "true";
      this.navMenu.setAttribute("data-open", isOpen ? "false" : "true");
      
      // Prevent body scroll when menu is open
      if (isOpen) {
        document.body.style.overflow = "";
      } else {
        document.body.style.overflow = "hidden";
      }
    }

    closeMenu() {
      if (!this.navMenu) return;
      this.navMenu.setAttribute("data-open", "false");
      document.body.style.overflow = "";
    }
  }

  // Scroll Animations - Modern reveal effects
  class ScrollAnimations {
    constructor() {
      this.fadeElements = document.querySelectorAll(".fade-in");
      this.sections = document.querySelectorAll(".answer-block, .quick-facts, .city-links, .faq");
      this.init();
    }

    init() {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      // Fade-in elements
      if (this.fadeElements.length > 0) {
        const fadeObserver = new IntersectionObserver(
          (entries) => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                entry.target.classList.add("visible");
              }
            });
          },
          { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
        );

        this.fadeElements.forEach(el => fadeObserver.observe(el));
      }

      // Section animations
      if (this.sections.length > 0) {
        const sectionObserver = new IntersectionObserver(
          (entries) => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                entry.target.classList.add("visible");
              }
            });
          },
          { threshold: 0.15, rootMargin: "0px 0px -100px 0px" }
        );

        this.sections.forEach(section => sectionObserver.observe(section));
      }
    }
  }

  // Navigation scroll effect
  class NavigationScroll {
    constructor() {
      this.nav = document.querySelector(".nav");
      this.init();
    }

    init() {
      if (!this.nav) return;

      let lastScroll = 0;
      window.addEventListener("scroll", () => {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > 50) {
          this.nav.classList.add("scrolled");
        } else {
          this.nav.classList.remove("scrolled");
        }

        lastScroll = currentScroll;
      });
    }
  }

  // Initialize on DOM ready
  // Hero Video Manager
  function setupHeroVideo() {
    const video = document.getElementById('hero-video');
    if (!video) return;

    const container = video.closest('.hero__video-container');
    if (!container) return;

    const poster = video.getAttribute('poster');
    
    // If video fails to load, background image will show (already set via inline style)
    video.addEventListener('error', function() {
      console.warn('Hero video failed to load, showing background image');
      // Background image is already set via inline style, so it will show automatically
    });

    // Try to play video (may fail due to autoplay policies)
    video.addEventListener('loadeddata', function() {
      video.play().then(function() {
        // Video is playing, show it
        video.classList.add('playing');
      }).catch(function(error) {
        console.warn('Video autoplay failed:', error);
        // Video stays hidden, background image shows
      });
    });

    // Show video when it starts playing
    video.addEventListener('playing', function() {
      video.classList.add('playing');
    });
    
    // Fallback: if video doesn't load within 3 seconds, ensure background shows
    setTimeout(function() {
      if (video.readyState < 2) { // HAVE_CURRENT_DATA
        console.warn('Video taking too long to load, background image will show');
        // Background image is already set via inline style
      }
    }, 3000);
  }

  function init() {
    // Setup hero video with fallback to background image
    setupHeroVideo();

    // Initialize Storage Manager (leads endpoint from form data-leads-endpoint, else API/localStorage)
    const storageMode = document.body.dataset.storageMode || "python";
    const form = document.querySelector("#notify-form, [data-form]");
    const leadsEndpoint = form?.dataset?.leadsEndpoint || "";
    const StorageManager = window.StorageManager || (() => {
      return {
        submit: async () => ({ success: false, error: "Storage manager not loaded" }),
        hasSubmitted: () => false,
        markAsSubmitted: () => {},
        hasModalShownThisSession: () => false,
        markModalAsShown: () => {},
        getStoredReferralCode: () => null,
        clearStoredReferralCode: () => {}
      };
    })();
    const storageManager = new StorageManager(storageMode, leadsEndpoint);

    // Initialize Referral Manager (if available)
    if (window.ReferralManager) {
      window.referralManager = new ReferralManager();
    }

    // Initialize Hero Tabs (must be before modal to track context)
    const heroTabsManager = new HeroTabsManager();

    // Initialize Modal
    const modalManager = new ModalManager("#notify-modal");

    // Initialize Form
    const formManager = new FormManager("#notify-form", storageManager);

    // Initialize Navigation
    const navManager = new NavigationManager();

    // Update form trigger handlers to pass context and opener for focus return
    const formTriggers = document.querySelectorAll("[data-form-trigger]");
    formTriggers.forEach(trigger => {
      trigger.addEventListener("click", (e) => {
        e.preventDefault();
        // Get context from hero CTA or default to players
        const context = trigger.getAttribute("data-hero-cta") || 
                       heroTabsManager.getCurrentContext() || 
                       "players";
        modalManager.open(context, { trigger: e.currentTarget });
      });
    });

    // Initialize Scroll Animations
    const scrollAnimations = new ScrollAnimations();

    // Initialize Navigation Scroll Effect
    const navScroll = new NavigationScroll();

    // Auto-open modal on page load (once per session, if not already submitted)
    if (!storageManager.hasSubmitted() && !storageManager.hasModalShownThisSession()) {
      const autoOpen = document.body.dataset.autoOpenModal !== "false";
      if (autoOpen) {
        setTimeout(() => {
          const context = heroTabsManager.getCurrentContext() || "players";
          modalManager.open(context);
          storageManager.markModalAsShown();
        }, 500);
      }
    }

    // Share link functionality (legacy - now handled by referral system)
    document.querySelector("[data-share-link]")?.addEventListener("click", () => {
      const url = window.location.href;
      const siteName = document.body.getAttribute("data-site-name") || "Atlanta Soccer Hub";
      if (navigator.share) {
        navigator.share({
          title: `Join ${siteName}`,
          text: `Check out ${siteName} - find, organize, and play pickup soccer in ${document.body.getAttribute("data-hub-marketing-name") || "Metro Atlanta"}!`,
          url: url
        });
      } else {
        navigator.clipboard.writeText(url).then(() => {
          alert("Link copied to clipboard!");
        });
      }
    });

    // Leaderboard functionality
    document.querySelector("[data-referral-leaderboard]")?.addEventListener("click", async () => {
      if (!window.referralManager) {
        window.referralManager = new ReferralManager();
      }
      
      const leaderboardResult = await window.referralManager.getLeaderboard(50);
      
      if (leaderboardResult.success) {
        // Create and show leaderboard modal
        const modal = document.createElement("div");
        modal.className = "modal";
        modal.setAttribute("aria-hidden", "false");
        modal.innerHTML = `
          <div class="modal__backdrop" data-modal-close></div>
          <div class="modal__content">
            <button class="modal__close" data-modal-close aria-label="Close">×</button>
            <h2 class="modal__title">Referral Leaderboard</h2>
            <div class="leaderboard">
              ${leaderboardResult.leaderboard.length > 0 
                ? leaderboardResult.leaderboard.map((entry, idx) => `
                  <div class="leaderboard__entry">
                    <span class="leaderboard__rank">#${entry.rank}</span>
                    <span class="leaderboard__email">${entry.email}</span>
                    <span class="leaderboard__count">${entry.referral_count} referrals</span>
                    ${entry.badges && entry.badges.length > 0 
                      ? `<div class="leaderboard__badges">${entry.badges.map(b => `<span class="badge badge--${b}">${window.referralManager.getBadgeLabel(b)}</span>`).join("")}</div>`
                      : ""
                    }
                  </div>
                `).join("")
                : "<p>No referrals yet. Be the first!</p>"
              }
            </div>
          </div>
        `;
        
        document.body.appendChild(modal);
        document.body.style.overflow = "hidden";
        
        // Close handlers
        modal.querySelectorAll("[data-modal-close]").forEach(btn => {
          btn.addEventListener("click", () => {
            document.body.removeChild(modal);
            document.body.style.overflow = "";
          });
        });
      }
    });

    // FAQ accordion
    document.querySelectorAll(".faq-item__question").forEach(question => {
      question.addEventListener("click", () => {
        const item = question.closest(".faq-item");
        const isExpanded = item.getAttribute("data-expanded") === "true";
        item.setAttribute("data-expanded", !isExpanded);
      });
    });

    // Update "Back to Blog" link based on referrer (uses injected base path)
    const blogBackLink = document.querySelector("[data-blog-back-link]");
    if (blogBackLink && document.referrer) {
      try {
        const basePath = (typeof window.__BASE_PATH !== "undefined" && window.__BASE_PATH) ? window.__BASE_PATH : "/";
        const referrerUrl = new URL(document.referrer);
        const referrerPath = referrerUrl.pathname;

        // If referrer is another blog post or blog listing, back link goes to hub #blog
        if (referrerPath.includes("/blog/")) {
          blogBackLink.href = (basePath === "/" ? "" : basePath) + "/#blog";
        } else {
          // Pattern: {basePath}/{location-slug}/ or {basePath}/{location-slug}/{area-slug}/
          const pathEscaped = basePath.replace(/\//g, "\\/");
          const locationMatch = referrerPath.match(new RegExp("^" + pathEscaped + "\\/([^/]+)(?:\\/([^/]+))?\\/?$"));

          if (locationMatch) {
            const citySlug = locationMatch[1];
            const areaSlug = locationMatch[2];
            // Never treat "blog" as a city slug — that would point to /blog/...#blog
            if (citySlug === "blog") {
              blogBackLink.href = (basePath === "/" ? "" : basePath) + "/#blog";
            } else if (areaSlug && areaSlug !== "blog") {
              blogBackLink.href = `${basePath}/${citySlug}/${areaSlug}/#blog`;
            } else if (citySlug) {
              blogBackLink.href = `${basePath}/${citySlug}/#blog`;
            } else {
              blogBackLink.href = (basePath === "/" ? "" : basePath) + "/#blog";
            }
          } else {
            blogBackLink.href = (basePath === "/" ? "" : basePath) + "/#blog";
          }
        }
      } catch (e) {
        const basePath = (typeof window.__BASE_PATH !== "undefined" && window.__BASE_PATH) ? window.__BASE_PATH : "/";
        blogBackLink.href = (basePath === "/" ? "" : basePath) + "/#blog";
      }
    }
  }

  // Run when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

