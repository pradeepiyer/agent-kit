// API Configuration
const API_URL = '/api/v1';

// Configure marked for GitHub Flavored Markdown
marked.setOptions({
  gfm: true,
  breaks: true,
});

// Alpine.js app component
function app() {
  return {
    // State
    agents: [],
    selectedAgent: null,
    agentName: 'Agent',
    token: null,
    sessionId: null,
    messages: [],
    inputValue: '',
    isLoading: true,
    isProcessing: false,

    // Initialize
    async init() {
      // Set page title
      document.title = 'Agent Kit';

      // Fetch agent info
      const info = await this.getAgentInfo();

      // Store available agents
      this.agents = info.agents || [];

      // Set selected agent (from localStorage or first agent)
      const savedAgentName = localStorage.getItem('selected_agent');
      if (savedAgentName && this.agents.find(a => a.name === savedAgentName)) {
        this.selectedAgent = this.agents.find(a => a.name === savedAgentName);
      } else if (this.agents.length > 0) {
        this.selectedAgent = this.agents[0];
      }

      // Set agent name and title
      if (this.selectedAgent) {
        this.agentName = this.selectedAgent.description;
        document.title = this.agentName;
      }

      // Check if auth is required
      if (!info.auth_required) {
        this.token = 'no-auth';
        this.isLoading = false;
        return;
      }

      // Handle OAuth callback
      if (window.location.pathname === '/callback') {
        this.token = this.handleCallback();
        this.isLoading = false;
        return;
      }

      // Check for existing token
      this.token = this.getToken();
      this.isLoading = false;
    },

    // Markdown rendering
    renderMarkdown(text) {
      if (!text) return '';
      const rawHtml = marked.parse(text);
      return DOMPurify.sanitize(rawHtml);
    },

    // Auto-scroll to bottom
    scrollToBottom() {
      this.$nextTick(() => {
        const messageList = this.$refs.messageList;
        if (messageList) {
          messageList.scrollTop = messageList.scrollHeight;
        }
      });
    },

    // Auto-grow textarea
    autoGrowTextarea() {
      this.$nextTick(() => {
        const textarea = this.$refs.textarea;
        if (textarea) {
          textarea.style.height = 'auto';
          textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        }
      });
    },

    // Handle Enter key
    handleEnter(event) {
      if (!event.shiftKey && this.inputValue.trim() && !this.isProcessing) {
        this.handleSend();
      }
    },

    // Handle send message
    async handleSend() {
      if (!this.inputValue.trim() || this.isProcessing) return;

      const content = this.inputValue;
      this.inputValue = '';
      this.autoGrowTextarea();

      // Add user message
      this.messages.push({ role: 'user', content });
      this.scrollToBottom();

      // Add assistant message placeholder
      this.messages.push({ role: 'assistant', content: '', isStreaming: true });
      this.scrollToBottom();

      this.isProcessing = true;

      try {
        await this.sendMessage(content, this.sessionId, this.token, (event) => {
          if (event.type === 'progress' && event.message) {
            // Replace progress message
            const lastMsg = this.messages[this.messages.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              lastMsg.content = event.message;
              this.scrollToBottom();
            }
          } else if (event.type === 'result' && event.data) {
            // Replace with final result
            const lastMsg = this.messages[this.messages.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              lastMsg.content = event.data.response;
              lastMsg.isStreaming = false;
              this.scrollToBottom();
            }
            if (event.data.session_id) {
              this.sessionId = event.data.session_id;
            }
            this.isProcessing = false;
          } else if (event.type === 'error') {
            // Show error
            const lastMsg = this.messages[this.messages.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              lastMsg.content = `Error: ${event.error || 'Unknown error'}`;
              lastMsg.isStreaming = false;
              this.scrollToBottom();
            }
            this.isProcessing = false;
          }
        });
      } catch (error) {
        const lastMsg = this.messages[this.messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = `Error: ${error.message || 'Failed to send message'}`;
          lastMsg.isStreaming = false;
          this.scrollToBottom();
        }
        this.isProcessing = false;
      }
    },

    // Handle new chat
    async handleNewChat() {
      this.messages = [];
      this.sessionId = null;
      try {
        const session = await this.createSession(this.token);
        this.sessionId = session.session_id;
      } catch (error) {
        console.error('Failed to create session:', error);
      }
    },

    // Handle agent selection
    selectAgent(agentName) {
      const agent = this.agents.find(a => a.name === agentName);
      if (!agent) return;

      this.selectedAgent = agent;
      this.agentName = agent.description;
      document.title = this.agentName;

      // Save selection
      localStorage.setItem('selected_agent', agentName);

      // Clear conversation when switching agents
      this.messages = [];
      this.sessionId = null;
    },

    // Handle logout
    handleLogout() {
      this.clearToken();
      window.location.reload();
    },

    // API: Get agent info
    async getAgentInfo() {
      const response = await fetch(`${API_URL}/info`);
      if (!response.ok) throw new Error('Failed to fetch agent info');
      return response.json();
    },

    // API: Create session
    async createSession(token) {
      const headers = this.buildHeaders(token);
      const response = await fetch(`${API_URL}/sessions`, {
        method: 'POST',
        headers,
      });
      if (!response.ok) throw new Error(`Failed to create session: ${response.statusText}`);
      return response.json();
    },

    // API: Send message with SSE
    async sendMessage(query, sessionId, token, onEvent) {
      if (!this.selectedAgent) {
        throw new Error('No agent selected');
      }

      const headers = this.buildHeaders(token);
      const response = await fetch(`${API_URL}/${this.selectedAgent.name}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query,
          session_id: sessionId,
        }),
      });

      if (!response.ok) throw new Error(`Failed to send message: ${response.statusText}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.substring(6);
              if (data.startsWith(':')) continue;

              try {
                const event = JSON.parse(data);
                onEvent(event);
              } catch (error) {
                console.error('Failed to parse SSE event:', error);
              }
            }
          }
        }
      } catch (error) {
        console.error('Stream reading error:', error);
        onEvent({ type: 'error', error: 'Connection error' });
      }
    },

    // Build headers
    buildHeaders(token) {
      const headers = {
        'Content-Type': 'application/json',
      };
      if (token && token !== 'no-auth') {
        headers['Authorization'] = `Bearer ${token}`;
      }
      return headers;
    },

    // Auth: Get token from localStorage
    getToken() {
      return localStorage.getItem('auth_token');
    },

    // Auth: Set token
    setToken(token) {
      localStorage.setItem('auth_token', token);
    },

    // Auth: Clear token
    clearToken() {
      localStorage.removeItem('auth_token');
    },

    // Auth: Redirect to login
    redirectToLogin() {
      const clientId = 'your-client-id'; // This should come from config
      const redirectUri = `${window.location.origin}/callback`;
      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=token&scope=openid%20email%20profile`;
      window.location.href = authUrl;
    },

    // Auth: Handle OAuth callback
    handleCallback() {
      const hash = window.location.hash.substring(1);
      const params = new URLSearchParams(hash);
      const token = params.get('access_token');

      if (token) {
        this.setToken(token);
        window.history.replaceState({}, document.title, '/');
        return token;
      }

      return null;
    },
  };
}
