import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Tabs, Tab, TabList, TabPanel, TabPanels } from "@carbon/react";

import type { UserPublic } from "../../client";
import Appearance from "../../components/user-settings/Appearance";
import DeleteAccount from "../../components/user-settings/DeleteAccount";
import UserInformation from "../../components/user-settings/UserInformation";

const tabsConfig = [
  { title: "My profile", component: UserInformation },
  { title: "Appearance", component: Appearance },
  { title: "Danger zone", component: DeleteAccount },
];

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
});

function UserSettings() {
  const queryClient = useQueryClient();
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"]);
  // TODO: Fix SUPER-USER Problem
  // const finalTabs = currentUser?.is_superuser
  //   ? tabsConfig.slice(0, 3)
  //   : tabsConfig;
  const finalTabs = currentUser ? tabsConfig.slice(0, 3) : tabsConfig;

  return (
    <div className="min-w-96">
      <h1 className="py-12 text-2xl font-bold">User Settings</h1>
      <Tabs>
        <TabList className="" aria-label="User Settings">
          {finalTabs.map((tab, index) => (
            <Tab key={index}>{tab.title}</Tab>
          ))}
        </TabList>
        <TabPanels>
          {finalTabs.map((tab, index) => (
            <TabPanel key={index}>
              <tab.component />
            </TabPanel>
          ))}
        </TabPanels>
      </Tabs>
    </div>
  );
}
