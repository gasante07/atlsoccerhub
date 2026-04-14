# NYC Soccer Hub Design System

A scalable, minimalistic design system built with CSS custom properties and component-based architecture. Features a football-themed grass green color palette.

## Table of Contents

1. [Design Tokens](#design-tokens)
2. [Components](#components)
3. [Utilities](#utilities)
4. [Layout](#layout)
5. [Typography](#typography)
6. [Spacing](#spacing)
7. [Colors](#colors)
8. [Usage Guidelines](#usage-guidelines)

---

## Design Tokens

### Colors

#### Primary Palette
```css
--color-black: #000000
--color-white: #FFFFFF
--color-gray-50 through --color-gray-900 (grayscale scale)
```

#### Accent Colors (Football-Themed)
```css
--color-primary: #03631F        /* Logo grass green */
--color-primary-dark: #024A17   /* Darker for hover/active */
--color-primary-light: #047A28  /* Lighter for highlights */
--color-accent: #1A1A1A         /* Charcoal complementary */
--color-accent-light: #404040   /* Lighter charcoal */
--color-success: #10B981        /* Success green */
--color-warning: #F59E0B        /* Warning amber */
```

#### Semantic Colors
```css
--color-text: var(--color-gray-900)
--color-text-light: var(--color-gray-600)
--color-text-muted: var(--color-gray-500)
--color-bg: var(--color-white)
--color-bg-alt: var(--color-gray-50)
--color-bg-dark: var(--color-gray-900)
```

### Typography

#### Font Families (Minimalistic System Fonts)
```css
--font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif
--font-family-display: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif
```

#### Font Weights (Simplified)
```css
--font-weight-normal: 400
--font-weight-medium: 500
--font-weight-semibold: 600
--font-weight-bold: 700
```

#### Font Sizes (Fluid Typography)
```css
--font-size-base: clamp(1rem, 0.9vw + 0.8rem, 1.125rem)
--font-size-h1: clamp(2.5rem, 8vw + 1rem, 6rem)
--font-size-h2: clamp(2rem, 5vw + 0.5rem, 4rem)
--font-size-h3: clamp(1.5rem, 3vw + 0.5rem, 2.5rem)
--font-size-h4: clamp(1.25rem, 2vw + 0.5rem, 1.75rem)
--font-size-large: clamp(1.25rem, 2vw + 0.5rem, 1.5rem)
```

#### Letter Spacing
```css
--letter-spacing-tight: -0.02em
--letter-spacing-normal: 0
--letter-spacing-wide: 0.05em
```

### Spacing Scale

```css
--space-xs: 0.5rem    /* 8px */
--space-sm: 1rem      /* 16px */
--space-md: 2rem      /* 32px */
--space-lg: 4rem      /* 64px */
--space-xl: 6rem      /* 96px */
--space-xxl: 8rem     /* 128px */
```

### Shadows

```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
--shadow-base: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)
--shadow-md: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)
--shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)
--shadow-xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25)
--shadow-2xl: 0 35px 60px -15px rgba(0, 0, 0, 0.3)
```

### Border Radius

```css
--radius-sm: 0.375rem    /* 6px */
--radius-base: 0.5rem    /* 8px */
--radius-md: 0.75rem     /* 12px */
--radius-lg: 1rem        /* 16px */
--radius-xl: 1.5rem      /* 24px */
--radius-full: 9999px
```

### Transitions

```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-base: 300ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-bounce: 400ms cubic-bezier(0.68, -0.55, 0.265, 1.55)
--transition-spring: 600ms cubic-bezier(0.34, 1.56, 0.64, 1)
```

### Breakpoints

```css
--bp-mobile-max: 767px
--bp-tablet-min: 768px
--bp-tablet-max: 1023px
--bp-desktop-min: 1024px
--bp-lg: 1280px
--bp-xl: 1440px
```

---

## Components

### Buttons

#### Base Button
```html
<button class="btn">Button</button>
```

#### Button Variants
```html
<button class="btn btn--primary">Primary</button>
<button class="btn btn--secondary">Secondary</button>
<button class="btn btn--primary btn--large">Large Button</button>
```

**Modifiers:**
- `.btn--primary` - Black background, white text
- `.btn--secondary` - White background, black text
- `.btn--large` - Larger padding and font size

### Forms

#### Form Field
```html
<div class="form__field">
  <label for="email" class="form__label">Email <span class="form__required">*</span></label>
  <input type="email" id="email" class="form__input" required>
  <span class="form__error" data-field-error="email"></span>
</div>
```

#### Form Input Types
- `.form__input` - Text inputs
- `.form__select` - Dropdown selects
- `.form__textarea` - Text areas
- `.form__checkbox` - Checkboxes

#### Form Layout
```html
<!-- Two-column layout on desktop -->
<div class="form__fields-row">
  <div class="form__field">...</div>
  <div class="form__field">...</div>
</div>
```

### Modal

```html
<div class="modal" data-modal id="notify-modal" aria-hidden="true">
  <div class="modal__backdrop" data-modal-close></div>
  <div class="modal__content">
    <button class="modal__close" data-modal-close>×</button>
    <h2 class="modal__title">Title</h2>
    <p class="modal__description">Description</p>
    <!-- Content -->
  </div>
</div>
```

### Navigation

```html
<header class="nav" data-nav>
  <div class="nav__container">
    <a href="/" class="nav__logo">Logo</a>
    <nav class="nav__menu">
      <a href="/" class="nav__link">Link</a>
      <button class="nav__cta btn btn--primary">CTA</button>
    </nav>
  </div>
</header>
```

### Hero Section

```html
<section class="hero">
  <div class="hero__video-container">
    <video class="hero__video" autoplay muted loop></video>
    <div class="hero__overlay"></div>
  </div>
  <div class="hero__content">
    <h1 class="hero__title">Title</h1>
    <p class="hero__subtitle">Subtitle</p>
    <p class="hero__description">Description</p>
    <button class="hero__cta btn btn--primary btn--large">CTA</button>
  </div>
</section>
```

### Cards

#### City Link Card
```html
<a href="/city/" class="city-link">
  <div class="city-link__image">
    <img src="image.jpg" alt="City">
  </div>
  <div class="city-link__text">City Name</div>
</a>
```

### FAQ Accordion

```html
<div class="faq-item" data-expanded="false">
  <h3 class="faq-item__question">Question?</h3>
  <div class="faq-item__answer">Answer</div>
</div>
```

---

## Utilities

### Container

```html
<div class="container">
  <!-- Full width container -->
</div>

<div class="container container--content">
  <!-- Max-width constrained container -->
</div>
```

### Spacing Utilities

Use design tokens directly:
```css
padding: var(--space-md);
margin-bottom: var(--space-lg);
gap: var(--space-xl);
```

### Text Utilities

```css
/* Text colors */
color: var(--color-text);
color: var(--color-text-light);
color: var(--color-text-muted);

/* Text alignment */
text-align: left;
text-align: center;
text-align: right;
```

---

## Layout

### Grid System

#### City Links Grid
```html
<div class="city-links__grid">
  <!-- Auto-responsive grid: 1 col mobile, 2 col tablet, 3 col desktop -->
</div>
```

#### Form Fields Row
```html
<div class="form__fields-row">
  <!-- Two-column layout on desktop, stacked on mobile -->
</div>
```

---

## Typography

### Headings

All headings use fluid typography and tight letter spacing:

```html
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h3>Heading 3</h3>
<h4>Heading 4</h4>
```

### Body Text

```html
<p>Body text uses --font-size-base with line-height: 1.7</p>
```

---

## Usage Guidelines

### Do's ✅

- Use design tokens for all spacing, colors, and typography
- Follow BEM naming convention for components
- Use semantic HTML elements
- Maintain consistent spacing using the spacing scale
- Use fluid typography with `clamp()` for responsive text
- Follow mobile-first approach

### Don'ts ❌

- Don't use hardcoded colors or spacing values
- Don't create new components without following naming conventions
- Don't skip the design token system
- Don't use arbitrary values - use the predefined scale
- Don't break the component structure

### Component Naming Convention

Follow BEM (Block Element Modifier) pattern:

```css
.block {}
.block__element {}
.block--modifier {}
.block__element--modifier {}
```

Examples:
- `.btn` (block)
- `.btn--primary` (modifier)
- `.form__field` (block__element)
- `.city-link__image` (block__element)

### Responsive Design

Always use mobile-first approach:

```css
/* Mobile styles (default) */
.component {
  /* Mobile styles */
}

/* Tablet and up */
@media (min-width: 768px) {
  .component {
    /* Tablet styles */
  }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .component {
    /* Desktop styles */
  }
}
```

### Accessibility

- Always include proper ARIA labels
- Use semantic HTML
- Ensure proper focus states
- Maintain color contrast ratios
- Support keyboard navigation

---

## Extending the Design System

### Adding New Colors

Add to `:root` in CSS:
```css
--color-new: #HEXCODE;
```

### Adding New Components

1. Create component class following BEM convention
2. Use design tokens for styling
3. Document in this file
4. Add examples

### Adding New Spacing Values

Add to spacing scale:
```css
--space-xxxl: 10rem; /* If needed */
```

---

## Version History

- **v1.0** - Initial design system with Nike.com-inspired minimal aesthetic
- Mobile-first responsive architecture
- Component-based structure
- Comprehensive design tokens

---

## Resources

- [Nike.com Design Inspiration](https://www.nike.com)
- [BEM Methodology](http://getbem.com/)
- [CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
- [Fluid Typography](https://css-tricks.com/snippets/css/fluid-typography/)

