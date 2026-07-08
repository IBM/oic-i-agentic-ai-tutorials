import { RadioButtonGroup, RadioButton, Tile, Tag } from "@carbon/react";
import { useTheme } from "../theme/ThemeProvider";

const Appearance = () => {
  const { theme, setTheme } = useTheme();

  const handleThemeChange = (value: string) => {
    setTheme(value as "light" | "dark" | "system");
  };

  return (
    <Tile className="max-w-md">
      <h3 className="mb-4 text-lg font-medium">Appearance</h3>
      <RadioButtonGroup
        className="mt-4"
        name="theme-selection"
        valueSelected={theme}
        onChange={(value) =>
          handleThemeChange(value ? value.toString() : "system")
        }
        orientation="vertical"
      >
        <RadioButton
          id="light"
          labelText={
            <div className="flex items-center">
              <span className="mr-2">Light Mode</span>
              {theme === "light" && (
                <Tag type="blue" size="sm" className="my-0">
                  Default
                </Tag>
              )}
            </div>
          }
          value="light"
        />
        <RadioButton id="dark" labelText="Dark Mode" value="dark" />
        <RadioButton id="system" labelText="System Default" value="system" />
      </RadioButtonGroup>
    </Tile>
  );
};

export default Appearance;
