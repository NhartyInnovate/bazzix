# Bazzix Frontend

<p align="center">
  <img src="public/favicon-svg.svg" alt="Bazzix Logo" width="120"/>
</p>

<h3 align="center">Think Beyond.</h3>

<p align="center">
An intelligent workspace where AI helps you understand, organize, and expand your thinking.
</p>

---

## Overview

Bazzix is an AI-powered thinking workspace designed to help users brainstorm ideas, ask questions, and organize conversations in a clean, distraction-free interface.

This repository contains the frontend application built with React, TypeScript, and Vite. It communicates with the Bazzix backend API to provide authentication, conversation management, and real-time AI chat streaming.

---

## Features

- Secure user authentication
- Beautiful modern interface
- AI conversation workspace
- Real-time streaming responses
- Automatic conversation title generation
- Conversation history
- Session management
- Responsive design
- Dark theme
- Fast page navigation

---

## Tech Stack

- React
- TypeScript
- Vite
- TanStack Router
- TanStack Query
- Tailwind CSS
- shadcn/ui
- Cloudflare Pages (Deployment)

---

## Project Structure

```
frontend/
│
├── public/
├── src/
│   ├── components/
│   ├── routes/
│   ├── hooks/
│   ├── services/
│   ├── lib/
│   ├── context/
│   └── assets/
│
├── package.json
├── vite.config.ts
└── README.md
```

---

## Getting Started

### Clone the repository

```bash
git clone https://github.com/NhartyInnovate/bazzix-ai-workspace.git

cd bazzix-frontend
```

### Install dependencies

```bash
npm install
```

### Configure Environment Variables

Create a `.env` file.

Example:

```env
VITE_API_URL=http://localhost:8000
```

---

## Running the Project

Development

```bash
npm run dev
```

Production Build

```bash
npm run build
```

Preview Production Build

```bash
npm run preview
```

---

## Backend

The frontend requires the Bazzix Backend API to be running.

Backend Repository:

https://github.com/NhartyInnovate/bazzix

---

## Deployment

The frontend is optimized for deployment on Cloudflare Pages.

Build Command

```bash
npm run build
```

Output Directory

```
dist
```

Environment Variable

```env
VITE_API_URL=https://your-backend-url.onrender.com
```

---

## Screenshots

Coming soon.

---

## Roadmap

- Workspace search
- File uploads
- Markdown rendering
- Syntax highlighting
- Conversation pinning
- Conversation renaming
- Mobile optimizations
- AI model selection
- Rich document support

---

## Contributing

Contributions, suggestions, and feature requests are welcome.

Feel free to fork the repository and submit a Pull Request.

---

## License

This project is licensed under the MIT License.

---

## Author

**Aminu Abdulsalami**

GitHub:
https://github.com/NhartyInnovate

---

<p align="center">
Built to help people think beyond.
</p>
