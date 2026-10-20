import crypto from "crypto";

export const randomEmail = () =>
  `test_${crypto.randomBytes(4).toString("hex")}@example.com`;

export const randomTeamName = () =>
  `Team ${crypto.randomBytes(4).toString("hex")}`;

export const randomPassword = () =>
  `${crypto.randomBytes(8).toString("hex")}`;

export const slugify = (text: string) =>
  text
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]+/g, "");
