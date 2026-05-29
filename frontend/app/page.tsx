export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-accent mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M12 3V21M4 7.5L20 16.5M20 7.5L4 16.5" stroke="white" strokeWidth="1.5" strokeOpacity="0.4"/>
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-text-main">SiteDoc</h1>
          <p className="mt-1 text-sm text-text-sub">AI-редактор для вашего сайта</p>
        </div>

        {/* Cards */}
        <div className="space-y-3">
          <a
            href="/login"
            className="flex items-center justify-between w-full bg-accent hover:bg-accent-hover text-white rounded-xl px-5 py-3.5 font-medium transition-colors"
          >
            <span>Войти</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 12L10 8L6 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>
          <a
            href="/register"
            className="flex items-center justify-between w-full bg-surface hover:bg-surface-3 border border-border text-text-main rounded-xl px-5 py-3.5 font-medium transition-colors shadow-card"
          >
            <span>Создать аккаунт</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 12L10 8L6 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>
        </div>
      </div>
    </main>
  );
}
