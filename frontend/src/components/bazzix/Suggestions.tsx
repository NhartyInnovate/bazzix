import { Code2, Lightbulb, Map, PenLine } from "lucide-react";

export const SUGGESTION_COLLECTIONS = [
  {
    name: "Developer Set",
    categories: [
      {
        title: "Code & Architecture",
        icon: Code2,
        suggestions: [
          "Explain this code snippet",
          "Debug an error I'm getting",
          "Review this architecture",
        ],
      },
      {
        title: "Writing",
        icon: PenLine,
        suggestions: [
          "Write documentation for...",
          "Draft a technical blog post",
          "Improve the tone of this text",
        ],
      },
      {
        title: "Research",
        icon: Lightbulb,
        suggestions: [
          "Explain a complex technical concept",
          "Summarize this long article",
          "Compare these two frameworks",
        ],
      },
      {
        title: "Planning",
        icon: Map,
        suggestions: [
          "Build a project roadmap",
          "Brainstorm edge cases for...",
          "Plan a database migration",
        ],
      },
    ],
  },
  {
    name: "Creator Set",
    categories: [
      {
        title: "Content Creation",
        icon: PenLine,
        suggestions: [
          "Draft a script for a video",
          "Write a thread about...",
          "Help me outline an essay",
        ],
      },
      {
        title: "Strategy",
        icon: Map,
        suggestions: [
          "Plan a launch strategy",
          "Create a content calendar",
          "Brainstorm audience engagement",
        ],
      },
      {
        title: "Research",
        icon: Lightbulb,
        suggestions: [
          "Find alternatives to...",
          "Explain the history of...",
          "Summarize key findings in...",
        ],
      },
      {
        title: "Technical",
        icon: Code2,
        suggestions: ["Write a regex for...", "Help me format this data", "Automate a workflow"],
      },
    ],
  },
];

export function getSuggestionCollection() {
  const dayOfWeek = new Date().getDay();
  return SUGGESTION_COLLECTIONS[dayOfWeek % SUGGESTION_COLLECTIONS.length];
}
