/**
 * Config-driven analytics: page views, clicks, form engagement.
 * Supports GA4 (when ga4MeasurementId is set) and/or custom events endpoint.
 */
(function() {
  "use strict";

  var config = (typeof window.__TRACKING_CONFIG__ !== "undefined") ? window.__TRACKING_CONFIG__ : {};
  var enabled = !!config.enabled;
  var ga4Id = (config.ga4MeasurementId || "").trim();
  var eventsEndpoint = (config.eventsEndpoint || "").trim();
  var trackPageView = !!config.trackPageView;
  var trackClicks = !!config.trackClicks;
  var trackFormEngagement = !!config.trackFormEngagement;

  function getDefaultPayload() {
    return {
      page: window.location.pathname || "/",
      url: window.location.href,
      ts: new Date().toISOString()
    };
  }

  function sendToGA4(eventName, params) {
    if (!ga4Id || typeof gtag !== "function") return;
    var payload = Object.assign({}, getDefaultPayload(), params || {});
    gtag("event", eventName, payload);
  }

  function sendToCustomEndpoint(eventName, params) {
    if (!eventsEndpoint) return;
    var payload = {
      event: eventName,
      params: Object.assign({}, getDefaultPayload(), params || {})
    };
    try {
      fetch(eventsEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true
      }).catch(function() {});
    } catch (e) {}
  }

  function dispatchEvent(eventName, params) {
    if (!enabled) return;
    sendToGA4(eventName, params);
    sendToCustomEndpoint(eventName, params);
  }

  function trackEvent(eventName, params) {
    if (!enabled) return;
    if (!trackFormEngagement && /^(modal_open|form_submit|form_error)/.test(eventName)) return;
    dispatchEvent(eventName, params || {});
  }

  // Expose for modal/form and other callers
  window.trackEvent = trackEvent;

  if (!enabled) return;

  // GA4: load gtag if measurement ID is set
  if (ga4Id) {
    window.dataLayer = window.dataLayer || [];
    function gtag(){ dataLayer.push(arguments); }
    window.gtag = gtag;
    var script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + ga4Id;
    script.onload = function() {
      gtag("js", new Date());
      gtag("config", ga4Id, { send_page_view: false });
    };
    document.head.appendChild(script);
  }

  // Page view
  if (trackPageView) {
    var pvParams = getDefaultPayload();
    dispatchEvent("page_view", pvParams);
  }

  // Delegated click tracking
  if (trackClicks) {
    document.addEventListener("click", function(e) {
      var target = e.target.closest("a, button, [data-form-trigger], [data-hero-cta], [data-track]");
      if (!target) return;

      var category = target.getAttribute("data-track-category") || "engagement";
      var label = target.getAttribute("data-track-label") ||
        (target.getAttribute("data-hero-cta") && ("hero_cta_" + target.getAttribute("data-hero-cta"))) ||
        (target.getAttribute("data-form-trigger") !== null && "nav_cta") ||
        (target.tagName === "A" && (target.textContent || "").trim().slice(0, 80)) ||
        (target.tagName === "BUTTON" && (target.textContent || "").trim().slice(0, 80)) ||
        target.tagName.toLowerCase();

      var href = target.getAttribute("href");
      dispatchEvent("click", {
        category: category,
        label: label,
        href: href || undefined
      });
    }, true);
  }
})();
