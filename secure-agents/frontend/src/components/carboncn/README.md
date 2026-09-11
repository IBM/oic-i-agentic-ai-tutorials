# CarbonCN

[CarbonCN](https://carboncn.dev) is a fork of shadcn/ui that mimics the Carbon Design System. It provides customizable components that you can add to your project when the standard Carbon components don't meet your specific needs. You can use them in addition to the Carbon components as they are designed to work together.

## Usage

### Adding Components

Use the CarbonCN CLI to add components to your UI folder:

```bash
npx carboncn add button
npx carboncn add dropdown
npx carboncn add dialog
```

### Customizing Components

Once added, you can modify the components in the `/ui` folder to fit your specific requirements. This is particularly useful when:

1. Carbon's default component behavior doesn't match your needs
2. You need to extend functionality beyond what Carbon provides
3. You want to maintain Carbon's visual language while customizing behavior

### Styling

Components can be styled using the Tailwind Carbon mapping:

_Note: you should install the tailwind intellisense plugin to get the best experience._

```tsx
<button className="bg-cds-button-primary text-cds-text-primary">
  Custom Button
</button>
```
