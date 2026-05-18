export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <h1 className="text-4xl font-semibold tracking-tight">MRKTGURU Agent</h1>
      <p className="mt-4 text-gray-400">
        AI-агент, который превращает идею в задеплоенный продукт.
      </p>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        <a
          href="/login"
          className="rounded-xl border border-gray-700 p-5 hover:border-accent transition"
        >
          <div className="text-lg font-medium">Войти</div>
          <div className="mt-1 text-sm text-gray-500">Уже есть аккаунт</div>
        </a>
        <a
          href="/register"
          className="rounded-xl border border-gray-700 p-5 hover:border-accent transition"
        >
          <div className="text-lg font-medium">Создать аккаунт</div>
          <div className="mt-1 text-sm text-gray-500">Поехали с нуля</div>
        </a>
      </div>
    </main>
  );
}
