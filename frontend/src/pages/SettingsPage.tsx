import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { OrgProfile } from '../types'

export default function SettingsPage() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [profile, setProfile] = useState<OrgProfile | null>(null)
  const [profileForm, setProfileForm] = useState({
    legal_name: '',
    trade_name: '',
    gstin: '',
    pan: '',
    default_state_code: '',
    phone: '',
    address: '',
    footer_note: '',
  })
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileMessage, setProfileMessage] = useState<string | null>(null)
  const [savingProfile, setSavingProfile] = useState(false)
  const [uploadingLogo, setUploadingLogo] = useState(false)

  useEffect(() => {
    apiClient
      .get<OrgProfile>('/org/profile')
      .then(({ data }) => {
        setProfile(data)
        setProfileForm({
          legal_name: data.legal_name ?? '',
          trade_name: data.trade_name ?? '',
          gstin: data.gstin ?? '',
          pan: data.pan ?? '',
          default_state_code: data.default_state_code ?? '',
          phone: data.phone ?? '',
          address: data.address ?? '',
          footer_note: data.footer_note ?? '',
        })
      })
      .catch(() => setProfile(null))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setMessage(null)
    if (form.new_password.length < 8) {
      setError('New password must be at least 8 characters.')
      return
    }
    if (form.new_password !== form.confirm) {
      setError('New passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await apiClient.post('/auth/change-password', {
        current_password: form.current_password,
        new_password: form.new_password,
      })
      setMessage('Password updated.')
      setForm({ current_password: '', new_password: '', confirm: '' })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    setProfileError(null)
    setProfileMessage(null)
    if (!profileForm.legal_name.trim()) {
      setProfileError('Legal name is required.')
      return
    }
    if (!/^[A-Z]{2}$/i.test(profileForm.default_state_code)) {
      setProfileError('State code must be a 2-letter code, e.g. MH.')
      return
    }
    const gstin = profileForm.gstin.trim()
    if (gstin && !/^[0-9A-Z]{15}$/i.test(gstin)) {
      setProfileError('GSTIN must be 15 alphanumeric characters.')
      return
    }
    const pan = profileForm.pan.trim()
    if (pan && !/^[A-Z]{5}[0-9]{4}[A-Z]$/i.test(pan.toUpperCase())) {
      setProfileError('PAN must match the format ABCDE1234F.')
      return
    }
    setSavingProfile(true)
    try {
      const { data } = await apiClient.patch<OrgProfile>('/org/profile', {
        legal_name: profileForm.legal_name.trim(),
        trade_name: profileForm.trade_name.trim() || null,
        gstin: gstin || null,
        pan: pan.toUpperCase() || null,
        default_state_code: profileForm.default_state_code.trim().toUpperCase(),
        phone: profileForm.phone.trim() || null,
        address: profileForm.address.trim() || null,
        footer_note: profileForm.footer_note.trim() || null,
      })
      setProfile(data)
      setProfileMessage('Business profile updated. Receipts will use the new details.')
    } catch (err) {
      setProfileError(apiErrorMessage(err))
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleLogoUpload(file: File | undefined) {
    if (!file) return
    setUploadingLogo(true)
    setProfileError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await apiClient.post<OrgProfile>('/org/logo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setProfile(data)
      setProfileMessage('Logo updated.')
    } catch (err) {
      setProfileError(apiErrorMessage(err))
    } finally {
      setUploadingLogo(false)
    }
  }

  const inputClass =
    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Settings</h1>

      <div className="max-w-2xl rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-800">
        <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-slate-50">Business Profile</h2>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Used for tax invoices and printed receipts. The trade name, address and GSTIN below appear on every receipt.
        </p>
        {profileError && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{profileError}</p>}
        {profileMessage && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{profileMessage}</p>}

        <div className="mb-4 flex items-center gap-4">
          {profile?.has_logo ? (
            <img src={`/org/logo.png?t=${Date.now()}`} alt="Store logo" className="h-16 w-16 rounded-lg border border-slate-200 object-contain dark:border-slate-700" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-dashed border-slate-300 text-xs text-slate-400 dark:border-slate-600">
              No logo
            </div>
          )}
          <label className="cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
            {uploadingLogo ? 'Uploading...' : profile?.has_logo ? 'Replace logo' : 'Upload logo'}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              disabled={uploadingLogo}
              onChange={(e) => {
                handleLogoUpload(e.target.files?.[0])
                e.target.value = ''
              }}
            />
          </label>
        </div>

        <form onSubmit={handleProfileSave} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Legal name *</label>
            <input required value={profileForm.legal_name} onChange={(e) => setProfileForm({ ...profileForm, legal_name: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Trade name</label>
            <input value={profileForm.trade_name} onChange={(e) => setProfileForm({ ...profileForm, trade_name: e.target.value })} className={inputClass} placeholder="Shown on receipts" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">GSTIN</label>
            <input value={profileForm.gstin} onChange={(e) => setProfileForm({ ...profileForm, gstin: e.target.value.toUpperCase() })} className={inputClass} maxLength={15} placeholder="15 characters" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">PAN</label>
            <input value={profileForm.pan} onChange={(e) => setProfileForm({ ...profileForm, pan: e.target.value.toUpperCase() })} className={inputClass} maxLength={10} placeholder="ABCDE1234F" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">State code *</label>
            <input required value={profileForm.default_state_code} onChange={(e) => setProfileForm({ ...profileForm, default_state_code: e.target.value.toUpperCase() })} className={inputClass} maxLength={2} placeholder="e.g. MH" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Phone</label>
            <input value={profileForm.phone} onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })} className={inputClass} />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Address</label>
            <textarea value={profileForm.address} onChange={(e) => setProfileForm({ ...profileForm, address: e.target.value })} rows={2} className={inputClass} />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Receipt footer note</label>
            <textarea
              value={profileForm.footer_note}
              onChange={(e) => setProfileForm({ ...profileForm, footer_note: e.target.value })}
              rows={2}
              className={inputClass}
              placeholder="e.g. Goods once sold will not be taken back."
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={savingProfile}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {savingProfile ? 'Saving...' : 'Save Business Profile'}
            </button>
          </div>
        </form>
      </div>

      <div className="max-w-md rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-800">
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-50">Change Password</h2>
        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
        {message && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Current password</label>
            <input
              type="password"
              required
              value={form.current_password}
              onChange={(e) => setForm({ ...form, current_password: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">New password</label>
            <input
              type="password"
              required
              value={form.new_password}
              onChange={(e) => setForm({ ...form, new_password: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Confirm new password</label>
            <input
              type="password"
              required
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {submitting ? 'Updating...' : 'Update Password'}
          </button>
        </form>
      </div>
    </div>
  )
}