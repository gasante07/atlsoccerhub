# Component Structure Guide

This document outlines the component structure and how to create new components following the design system.

## Component Organization

```
src/styles/
├── main.css              # Main compiled stylesheet (imports all)
├── tokens.css            # Design tokens (CSS variables)
├── base.css              # Reset and base styles
├── components/           # Component styles
│   ├── button.css
│   ├── form.css
│   ├── modal.css
│   ├── navigation.css
│   ├── hero.css
│   ├── card.css
│   └── ...
└── utilities/            # Utility classes
    ├── spacing.css
    ├── typography.css
    └── layout.css
```

## Creating a New Component

### Step 1: Create Component File

Create a new file in `src/styles/components/`:

```css
/* components/new-component.css */

/* Component Block */
.new-component {
  /* Base styles */
}

/* Component Elements */
.new-component__title {
  /* Element styles */
}

.new-component__content {
  /* Element styles */
}

/* Component Modifiers */
.new-component--large {
  /* Modifier styles */
}

.new-component--dark {
  /* Modifier styles */
}

/* Responsive Styles */
@media (min-width: 768px) {
  .new-component {
    /* Tablet styles */
  }
}

@media (min-width: 1024px) {
  .new-component {
    /* Desktop styles */
  }
}
```

### Step 2: Use Design Tokens

Always use design tokens instead of hardcoded values:

```css
/* ✅ Good */
.new-component {
  padding: var(--space-lg);
  color: var(--color-text);
  font-size: var(--font-size-base);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-md);
  transition: var(--transition-base);
}

/* ❌ Bad */
.new-component {
  padding: 64px;
  color: #1A1A1A;
  font-size: 18px;
  border-radius: 8px;
  box-shadow: 0 10px 15px rgba(0,0,0,0.1);
  transition: all 0.3s ease;
}
```

### Step 3: Follow BEM Naming

Use Block__Element--Modifier pattern:

```html
<!-- Block -->
<div class="card">
  <!-- Element -->
  <h2 class="card__title">Title</h2>
  <p class="card__content">Content</p>
  
  <!-- Element with Modifier -->
  <button class="card__button card__button--primary">Action</button>
</div>
```

### Step 4: Mobile-First Approach

Always write mobile styles first, then enhance for larger screens:

```css
/* Mobile (default) */
.component {
  padding: var(--space-md);
  font-size: var(--font-size-base);
}

/* Tablet and up */
@media (min-width: 768px) {
  .component {
    padding: var(--space-lg);
    font-size: var(--font-size-large);
  }
}

/* Desktop and up */
@media (min-width: 1024px) {
  .component {
    padding: var(--space-xl);
  }
}
```

### Step 5: Document the Component

Add to `DESIGN_SYSTEM.md`:

```markdown
### New Component

```html
<div class="new-component">
  <h2 class="new-component__title">Title</h2>
  <div class="new-component__content">Content</div>
</div>
```

**Modifiers:**
- `.new-component--large` - Larger variant
- `.new-component--dark` - Dark theme variant
```

## Component Checklist

When creating a new component, ensure:

- [ ] Uses design tokens for all values
- [ ] Follows BEM naming convention
- [ ] Mobile-first responsive design
- [ ] Includes accessibility considerations
- [ ] Has proper focus states
- [ ] Uses semantic HTML
- [ ] Documented in DESIGN_SYSTEM.md
- [ ] Tested across breakpoints
- [ ] Consistent with existing components

## Common Patterns

### Card Component Pattern

```css
.card {
  background: var(--color-white);
  padding: var(--space-lg);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-base);
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

### Button Component Pattern

```css
.btn {
  display: inline-block;
  padding: var(--space-sm) var(--space-md);
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
  transition: var(--transition-base);
  border: none;
  cursor: pointer;
}

.btn--primary {
  background: var(--color-black);
  color: var(--color-white);
}

.btn--primary:hover {
  opacity: 0.8;
}
```

### Form Component Pattern

```css
.form__field {
  margin-bottom: var(--space-md);
}

.form__label {
  display: block;
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-xs);
  text-transform: uppercase;
  font-size: 0.875rem;
  letter-spacing: var(--letter-spacing-wide);
}

.form__input {
  width: 100%;
  padding: var(--space-sm) 0;
  border: none;
  border-bottom: 1px solid var(--color-gray-300);
  transition: border-color var(--transition-fast);
}

.form__input:focus {
  outline: none;
  border-bottom-color: var(--color-black);
}
```

## Best Practices

1. **Consistency**: Use existing components as reference
2. **Reusability**: Create components that can be reused
3. **Composition**: Combine smaller components to build larger ones
4. **Accessibility**: Always consider accessibility first
5. **Performance**: Keep CSS minimal and efficient
6. **Documentation**: Document all components thoroughly

## Extending Existing Components

When extending an existing component:

1. Check if a modifier can solve the need
2. If not, create a new variant component
3. Maintain consistency with existing patterns
4. Update documentation

Example:

```css
/* Extend button with new variant */
.btn--outline {
  background: transparent;
  border: 2px solid var(--color-black);
  color: var(--color-black);
}

.btn--outline:hover {
  background: var(--color-black);
  color: var(--color-white);
}
```

