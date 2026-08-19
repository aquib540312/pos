import { Link } from 'react-router-dom'

export default function AccessDeniedPage({ message }: { message?: string }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Access denied</h1>
      <p className="mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
        {message ?? "You don't have permission to view this page. Ask an administrator to grant you the required role."}
      </p>
      <Link to="/" className="mt-6 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
        Go to your home page
      </Link>
    </div>
  )
}