import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ProductsPage from './pages/ProductsPage'
import CustomersPage from './pages/CustomersPage'
import POSPage from './pages/POSPage'
import SyncDashboardPage from './pages/SyncDashboardPage'
import ReportsPage from './pages/ReportsPage'
import ShiftPage from './pages/ShiftPage'
import StaffPage from './pages/StaffPage'
import SuppliersPage from './pages/SuppliersPage'
import PurchasingPage from './pages/PurchasingPage'
import StockTransferPage from './pages/StockTransferPage'
import BranchesPage from './pages/BranchesPage'
import AuditLogPage from './pages/AuditLogPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/pos" element={<POSPage />} />
            <Route path="/shift" element={<ShiftPage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/suppliers" element={<SuppliersPage />} />
            <Route path="/purchasing" element={<PurchasingPage />} />
            <Route path="/stock-transfer" element={<StockTransferPage />} />
            <Route path="/staff" element={<StaffPage />} />
            <Route path="/branches" element={<BranchesPage />} />
            <Route path="/audit-log" element={<AuditLogPage />} />
            <Route path="/sync" element={<SyncDashboardPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
