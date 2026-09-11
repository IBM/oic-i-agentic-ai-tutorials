import { Items } from "../../client";
import type { QueryClient } from "@tanstack/react-query";

// Track user messages by parentMessageId for feedback linking
const userMessageStore = new Map<string, string>();
const lastUserMessageByThread = new Map<string, string>();

// Create handlers factory that accepts queryClient
export const createHandlers = (queryClient: QueryClient) => {
  // Capture user messages temporarily by thread
  const sendHandler = (event: any) => {
    if (event.message?.thread_id && event.message?.message?.content) {
      lastUserMessageByThread.set(
        event.message.thread_id,
        event.message.message.content,
      );
    }
  };

  // Link assistant responses to user messages via parentMessageId
  const receiveHandler = (event: any) => {
    if (event.message?.parentMessageId && event.message?.threadId) {
      const userMessage = lastUserMessageByThread.get(event.message.threadId);
      if (userMessage) {
        userMessageStore.set(event.message.parentMessageId, userMessage);
      }
    }
  };

  // Save feedback to database
  const feedbackHandler = async (event: any) => {
    try {
      // Skip non-submitted negative feedback to avoid duplicates
      if (event.interactionType !== "submitted" && !event.isPositive) {
        return;
      }

      const feedbackData = {
        feedback_type: event.isPositive ? "positive" : "negative",
        feedback_comment: event.text || null,
        rated_message: event.messageItem?.text || null,
        user_message_before:
          userMessageStore.get(event.message?.parentMessageId) || null,
      };

      await Items.createItem({ body: feedbackData });
      queryClient.invalidateQueries({ queryKey: ["items"] });
    } catch (error) {
      console.error("Error saving feedback:", error);
    }
  };

  // Configure feedback options for each message
  const preReceiveHandler = (event: any) => {
    const lastItem =
      event?.message?.content?.[event.message.content.length - 1];
    if (lastItem) {
      lastItem.message_options = {
        feedback: {
          is_on: true,
          show_positive_details: false,
          show_negative_details: true,
          negative_options: {
            categories: [
              "Inaccurate",
              "Incomplete",
              "Too long",
              "Irrelevant",
              "Other",
            ],
            disclaimer: "Provide content that can be shared publicly.",
          },
        },
      };
    }
  };

  return {
    sendHandler,
    receiveHandler,
    feedbackHandler,
    preReceiveHandler,
  };
};
