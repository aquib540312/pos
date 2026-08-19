import { useEffect, useRef, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import { useCan, PERMS } from '../auth/permissions'
import type { BulkImportResponse, Category, HSN, Product, UOM } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
  is_default: boolean
}
interface Branch {
  id: string
  code: string
  name: string
  warehouses: Warehouse[]
}

const GST_SLABS = [0, 5, 12, 18, 28]

interface ProductForm {
  sku: string
  barcode: string
  generateBarcode: boolean
  name: string
  brand: string
  category_id: string
  uom_id: string
  hsn_code_id: string
  mrp: string
  sale_price: string
  wholesale_price: string
  purchase_price: string
  reorder_level: string
  tracks_batches: boolean
  tracks_serials: boolean
  tracks_expiry: boolean
  is_weighted: boolean
  prices_gst_inclusive: boolean
  loyalty_exempt: boolean
  low_stock_notify: boolean
  parent_product_id: string
  variant_label: string
  aliases: string
  initial_stock_qty: string
  warehouse_id: string
}

const EMPTY_FORM: ProductForm = {
  sku: '',
  barcode: '',
  generateBarcode: false,
  name: '',
  brand: '',
  category_id: '',
  uom_id: '',
  hsn_code_id: '',
  mrp: '',
  sale_price: '',
  wholesale_price: '',
  purchase_price: '',
  reorder_level: '',
  tracks_batches: false,
  tracks_serials: false,
  tracks_expiry: false,
  is_weighted: false,
  prices_gst_inclusive: false,
  loyalty_exempt: false,
  low_stock_notify: true,
  parent_product_id: '',
  variant_label: '',
  aliases: '',
  initial_stock_qty: '',
  warehouse_id: '',
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [uoms, setUoms] = useState<UOM[]>([])
  const [hsnCodes, setHsnCodes] = useState<HSN[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [labelProduct, setLabelProduct] = useState<Product | null>(null)
  const [labelCopies, setLabelCopies] = useState(12)
  const [printingLabels, setPrintingLabels] = useState(false)
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [bulkImportBusy, setBulkImportBusy] = useState(false)
  const [bulkImportError, setBulkImportError] = useState<string | null>(null)
  const [bulkImportResult, setBulkImportResult] = useState<BulkImportResponse | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<ProductForm>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [uploadingImage, setUploadingImage] = useState(false)
  const canManageCatalog = useCan(PERMS.CATALOG_MANAGE)

  async function loadProducts(q?: string) {
    const res = await apiClient.get<Product[]>('/catalog/products', { params: q ? { search: q } : {} })
    setProducts(res.data)
  }

  useEffect(() => {
    loadProducts()
    apiClient.get<UOM[]>('/catalog/uom').then((r) => setUoms(r.data))
    apiClient.get<HSN[]>('/catalog/hsn').then((r) => setHsnCodes(r.data))
    apiClient.get<Category[]>('/catalog/categories').then((r) => setCategories(r.data))
    apiClient
      .get<Branch[]>('/org/branches')
      .then((res) => setBranches(res.data))
      .catch(() => setBranches([]))
  }, [])

  function startEdit(p: Product) {
    setEditingId(p.id)
    setForm({
      sku: p.sku,
      barcode: p.barcode ?? '',
      generateBarcode: false,
      name: p.name,
      brand: p.brand ?? '',
      category_id: p.category_id ?? '',
      uom_id: p.uom_id,
      hsn_code_id: p.hsn_code_id ?? '',
      mrp: String(p.mrp),
      sale_price: String(p.sale_price),
      wholesale_price: String(p.wholesale_price ?? 0),
      purchase_price: String(p.purchase_price ?? 0),
      reorder_level: String(p.reorder_level ?? 0),
      tracks_batches: p.tracks_batches,
      tracks_serials: p.tracks_serials,
      tracks_expiry: p.tracks_expiry,
      is_weighted: p.is_weighted,
      prices_gst_inclusive: p.prices_gst_inclusive,
      loyalty_exempt: p.loyalty_exempt,
      low_stock_notify: p.low_stock_notify,
      parent_product_id: p.parent_product_id ?? '',
      variant_label: p.variant_label ?? '',
      aliases: p.aliases.join(', '),
      initial_stock_qty: '',
      warehouse_id: '',
    })
    setShowForm(true)
    setError(null)
  }

  function cancelForm() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowForm(false)
    setError(null)
  }

  async function handleUpdate(p: Product) {
    setError(null)
    try {
      const aliases = form.aliases.split(',').map((a) => a.trim()).filter(Boolean)
      await apiClient.patch(`/catalog/products/${p.id}`, {
        sku: form.sku,
        barcode: form.barcode || null,
        name: form.name,
        brand: form.brand || null,
        category_id: form.category_id || null,
        uom_id: form.uom_id,
        hsn_code_id: form.hsn_code_id || null,
        mrp: Number(form.mrp),
        sale_price: Number(form.sale_price),
        wholesale_price: Number(form.wholesale_price || 0),
        purchase_price: Number(form.purchase_price || 0),
        reorder_level: Number(form.reorder_level || 0),
        tracks_batches: form.tracks_batches,
        tracks_serials: form.tracks_serials,
        tracks_expiry: form.tracks_expiry,
        is_weighted: form.is_weighted,
        prices_gst_inclusive: form.prices_gst_inclusive,
        loyalty_exempt: form.loyalty_exempt,
        low_stock_notify: form.low_stock_notify,
        parent_product_id: form.parent_product_id || null,
        variant_label: form.variant_label || null,
        aliases: aliases,
      })
      cancelForm()
      loadProducts(search)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (editingId) {
      const existing = products.find((p) => p.id === editingId)
      if (existing) {
        await handleUpdate(existing)
      }
      return
    }
    try {
      const aliases = form.aliases.split(',').map((a) => a.trim()).filter(Boolean)
      await apiClient.post('/catalog/products', {
        sku: form.sku,
        barcode: form.barcode || null,
        generate_barcode: form.generateBarcode,
        name: form.name,
        brand: form.brand || null,
        category_id: form.category_id || null,
        uom_id: form.uom_id,
        hsn_code_id: form.hsn_code_id || null,
        mrp: Number(form.mrp),
        sale_price: Number(form.sale_price),
        wholesale_price: Number(form.wholesale_price || 0),
        purchase_price: Number(form.purchase_price || 0),
        reorder_level: Number(form.reorder_level || 0),
        tracks_batches: form.tracks_batches,
        tracks_serials: form.tracks_serials,
        tracks_expiry: form.tracks_expiry,
        is_weighted: form.is_weighted,
        prices_gst_inclusive: form.prices_gst_inclusive,
        loyalty_exempt: form.loyalty_exempt,
        low_stock_notify: form.low_stock_notify,
        parent_product_id: form.parent_product_id || null,
        variant_label: form.variant_label || null,
        aliases: aliases,
        initial_stock_qty: Number(form.initial_stock_qty || 0),
        warehouse_id: form.warehouse_id || null,
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      loadProducts(search)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  function pickGstSlab(rate: number) {
    const match = hsnCodes.find((h) => Math.round(h.current_rate_percent ?? -1) === rate)
    if (match) {
      setForm((f) => ({ ...f, hsn_code_id: match.id }))
      setError(null)
    } else {
      setError(`No HSN code at ${rate}% exists yet -- create one under HSN/SAC Codes first.`)
    }
  }

  async function handleImageUpload(file: File, productId: string) {
    setUploadingImage(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await apiClient.post(`/catalog/products/${productId}/image`, formData)
      loadProducts(search)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setUploadingImage(false)
    }
  }

  async function printLabelSheet() {
    if (!labelProduct) return
    setPrintingLabels(true)
    try {
      const res = await apiClient.get(`/catalog/products/${labelProduct.id}/label-sheet.png`, {
        params: { copies: labelCopies, columns: 3 },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data as Blob)
      const printWindow = window.open('', '_blank')
      if (printWindow) {
        printWindow.document.write(
          `<html><head><title>${labelProduct.name} labels</title></head>` +
            `<body style="margin:0"><img src="${url}" style="width:100%" onload="window.focus();window.print()" /></body></html>`,
        )
        printWindow.document.close()
      }
      setLabelProduct(null)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setPrintingLabels(false)
    }
  }

  async function downloadBulkImportTemplate() {
    const res = await apiClient.get('/catalog/products/bulk-import/template', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'product-import-template.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  }

  async function handleBulkImportFile(file: File) {
    setBulkImportBusy(true)
    setBulkImportError(null)
    setBulkImportResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await apiClient.post<BulkImportResponse>('/catalog/products/bulk-import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setBulkImportResult(res.data)
      loadProducts(search)
    } catch (err) {
      setBulkImportError(apiErrorMessage(err))
    } finally {
      setBulkImportBusy(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Products</h1>
        <div className="flex gap-2">
          {canManageCatalog && (
            <>
              <button
                onClick={() => {
                  setShowBulkImport((v) => !v)
                  setBulkImportError(null)
                  setBulkImportResult(null)
                }}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                Bulk Upload (Excel)
              </button>
              <button
                onClick={() => {
                  if (showForm) {
                    cancelForm()
                  } else {
                    setShowForm(true)
                  }
                }}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
              >
                {showForm ? 'Cancel' : editingId ? 'Editing...' : '+ New Product'}
              </button>
            </>
          )}
        </div>
      </div>

      {showBulkImport && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Upload an .xlsx file to create or update many products at once. A row with an existing SKU updates that
              product; a new SKU creates one.
            </p>
            <button
              onClick={downloadBulkImportTemplate}
              className="whitespace-nowrap text-sm font-medium text-indigo-600 hover:text-indigo-500"
            >
              Download template
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            disabled={bulkImportBusy}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleBulkImportFile(file)
            }}
            className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white file:hover:bg-indigo-500 dark:text-slate-300"
          />
          {bulkImportBusy && <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Uploading and processing...</p>}
          {bulkImportError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{bulkImportError}</p>}
          {bulkImportResult && (
            <div className="mt-4">
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {bulkImportResult.total} row(s): {bulkImportResult.created} created, {bulkImportResult.updated} updated,{' '}
                {bulkImportResult.failed} failed.
              </p>
              {bulkImportResult.failed > 0 && (
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-red-200 dark:border-red-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300">
                      <tr>
                        <th className="px-3 py-2">Row</th>
                        <th className="px-3 py-2">SKU</th>
                        <th className="px-3 py-2">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bulkImportResult.rows
                        .filter((r) => r.status === 'error')
                        .map((r) => (
                          <tr key={r.row} className="border-t border-red-100 dark:border-red-900">
                            <td className="px-3 py-2">{r.row}</td>
                            <td className="px-3 py-2">{r.sku ?? '-'}</td>
                            <td className="px-3 py-2 text-red-700 dark:text-red-300">{r.error}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4">
          <h2 className="col-span-full text-sm font-semibold text-slate-700 dark:text-slate-200">
            {editingId ? `Edit product (${products.find((p) => p.id === editingId)?.sku ?? ''})` : 'New product'}
          </h2>
          <input required placeholder="SKU *" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <div>
            <div className="flex gap-1">
              <input placeholder="Barcode (optional)" value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value, generateBarcode: false })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
              <button type="button" onClick={() => setForm((f) => ({ ...f, generateBarcode: !f.generateBarcode, barcode: f.generateBarcode ? '' : f.barcode }))} title="Auto-generate EAN-13 barcode" className={`shrink-0 rounded-lg px-2 text-sm font-semibold ${form.generateBarcode ? 'bg-indigo-600 text-white' : 'border border-slate-300 text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300'}`}>Auto</button>
            </div>
            {form.generateBarcode && <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">EAN-13 will be generated automatically.</p>}
            {form.barcode.trim().length > 0 && products.some((p) => p.barcode?.toLowerCase() === form.barcode.trim().toLowerCase()) && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">That barcode is already in use.</p>
            )}
          </div>
          <input required placeholder="Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Brand / Manufacturer" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Search aliases (comma)" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Category...</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select required value={form.uom_id} onChange={(e) => setForm({ ...form, uom_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Unit *</option>
            {uoms.map((u) => (
              <option key={u.id} value={u.id}>{u.code} - {u.name}</option>
            ))}
          </select>
          <div className="col-span-2">
            <select value={form.hsn_code_id} onChange={(e) => setForm({ ...form, hsn_code_id: e.target.value })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
              <option value="">HSN / GST rate...</option>
              {hsnCodes.map((h) => (
                <option key={h.id} value={h.id}>{h.code} ({h.current_rate_percent ?? '?'}%)</option>
              ))}
            </select>
            <div className="mt-1 flex flex-wrap gap-1">
              <span className="text-xs text-slate-400 dark:text-slate-500">Quick GST:</span>
              {GST_SLABS.map((rate) => (
                <button key={rate} type="button" onClick={() => pickGstSlab(rate)} className="rounded border border-slate-300 px-2 py-0.5 text-xs text-slate-600 hover:bg-indigo-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700">
                  {rate}%
                </button>
              ))}
            </div>
          </div>
          <input required type="number" step="0.01" placeholder="MRP *" value={form.mrp} onChange={(e) => setForm({ ...form, mrp: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input required type="number" step="0.01" placeholder="Sale price *" value={form.sale_price} onChange={(e) => setForm({ ...form, sale_price: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input type="number" step="0.01" placeholder="Wholesale price" value={form.wholesale_price} onChange={(e) => setForm({ ...form, wholesale_price: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input type="number" step="0.01" placeholder="Purchase price" value={form.purchase_price} onChange={(e) => setForm({ ...form, purchase_price: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input type="number" step="0.01" placeholder="Reorder level" value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input type="number" step="0.001" min="0" placeholder="Opening stock qty" value={form.initial_stock_qty} onChange={(e) => setForm({ ...form, initial_stock_qty: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select value={form.warehouse_id} onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Warehouse for opening stock...</option>
            {branches.flatMap((b) => b.warehouses).map((w) => (
              <option key={w.id} value={w.id}>{w.name} ({w.code})</option>
            ))}
          </select>
          <input placeholder="Variant label (e.g. M, Red)" value={form.variant_label} onChange={(e) => setForm({ ...form, variant_label: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select value={form.parent_product_id} onChange={(e) => setForm({ ...form, parent_product_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Variant of (parent product)...</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
            ))}
          </select>

          <div className="col-span-2 grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700 md:grid-cols-3">
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.tracks_batches} onChange={(e) => setForm({ ...form, tracks_batches: e.target.checked })} /> Batch tracking
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.tracks_serials} onChange={(e) => setForm({ ...form, tracks_serials: e.target.checked })} /> Serial tracking
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.tracks_expiry} onChange={(e) => setForm({ ...form, tracks_expiry: e.target.checked })} /> Expiry tracking
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.is_weighted} onChange={(e) => setForm({ ...form, is_weighted: e.target.checked })} /> Sold by weight
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.prices_gst_inclusive} onChange={(e) => setForm({ ...form, prices_gst_inclusive: e.target.checked })} /> Price includes GST
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.loyalty_exempt} onChange={(e) => setForm({ ...form, loyalty_exempt: e.target.checked })} /> No loyalty points
            </label>
            <label className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={form.low_stock_notify} onChange={(e) => setForm({ ...form, low_stock_notify: e.target.checked })} /> Low-stock alert
            </label>
          </div>

          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
            {editingId ? 'Update product' : 'Save product'}
          </button>
        </form>
      )}

      <div className="mb-4">
        <input
          placeholder="Search by name, SKU, barcode, brand, or alias..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            loadProducts(e.target.value)
          }}
          className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Photo</th>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Brand</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">MRP</th>
              <th className="px-4 py-3">Sale</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3">
                  {p.image_path ? (
                    <img src={`/api/v1/catalog/products/${p.id}/image.png`} alt={p.name} className="h-10 w-10 rounded object-cover" />
                  ) : (
                    <div className="flex h-10 w-10 items-center justify-center rounded bg-slate-100 text-xs text-slate-400 dark:bg-slate-700">—</div>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.sku}{p.variant_label ? ` · ${p.variant_label}` : ''}</td>
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{p.name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.brand ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.category_name ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{p.mrp.toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{p.sale_price.toFixed(2)}{p.prices_gst_inclusive ? ' (inc GST)' : ''}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  {canManageCatalog && (
                    <button
                      onClick={() => startEdit(p)}
                      className="mr-3 text-sm font-medium text-indigo-600 hover:text-indigo-500"
                    >
                      Edit
                    </button>
                  )}
                  {canManageCatalog && (
                    <label className="mr-3 cursor-pointer text-sm font-medium text-indigo-600 hover:text-indigo-500">
                      {uploadingImage ? 'Uploading...' : 'Photo'}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (file) {
                            handleImageUpload(file, p.id)
                          }
                          if (e.target) e.target.value = ''
                        }}
                      />
                    </label>
                  )}
                  <button
                    onClick={() => {
                      setLabelProduct(p)
                      setLabelCopies(12)
                    }}
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
                  >
                    Print labels
                  </button>
                </td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-400">No products found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {labelProduct && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl dark:bg-slate-800">
            <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-slate-50">Print labels</h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">{labelProduct.name}</p>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Number of labels
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={labelCopies}
              onChange={(e) => setLabelCopies(Number(e.target.value))}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setLabelProduct(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={printLabelSheet}
                disabled={printingLabels}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {printingLabels ? 'Generating...' : 'Print'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}