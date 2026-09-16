import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import RequirePermission from './components/RequirePermission'
import HomeRedirect from './components/HomeRedirect'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import BillingPage from './pages/BillingPage'
import DashboardPage from './pages/DashboardPage'
import ProductsPage from './pages/ProductsPage'
import CustomersPage from './pages/CustomersPage'
import POSPage from './pages/POSPage'
import RestaurantPage from './pages/RestaurantPage'
import RestaurantMenuPage from './pages/RestaurantMenuPage'
import SyncDashboardPage from './pages/SyncDashboardPage'
import ReportsPage from './pages/ReportsPage'
import ShiftPage from './pages/ShiftPage'
import StaffPage from './pages/StaffPage'
import RolesPage from './pages/RolesPage'
import SuppliersPage from './pages/SuppliersPage'
import PurchasingPage from './pages/PurchasingPage'
import StockTransferPage from './pages/StockTransferPage'
import BranchesPage from './pages/BranchesPage'
import AuditLogPage from './pages/AuditLogPage'
import QuotationsPage from './pages/QuotationsPage'
import SalesHistoryPage from './pages/SalesHistoryPage'
import StockPage from './pages/StockPage'
import OffersPage from './pages/OffersPage'
import SettingsPage from './pages/SettingsPage'
import { PERMS } from './auth/permissions'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<ProtectedRoute />}>
          <Route
            path="/restaurant-order"
            element={
              <RequirePermission permission={PERMS.DINING_MANAGE}>
                <RestaurantMenuPage />
              </RequirePermission>
            }
          />
          <Route element={<Layout />}>
            <Route
              path="/"
              element={
                <RequirePermission permission={PERMS.REPORTS_VIEW}>
                  <DashboardPage />
                </RequirePermission>
              }
            />
            <Route
              path="/pos"
              element={
                <RequirePermission permission={PERMS.SALES_CREATE}>
                  <POSPage />
                </RequirePermission>
              }
            />
            <Route
              path="/restaurant"
              element={
                <RequirePermission permission={PERMS.DINING_MANAGE}>
                  <RestaurantPage />
                </RequirePermission>
              }
            />
            <Route
              path="/quotations"
              element={
                <RequirePermission permission={PERMS.QUOTATION_CREATE}>
                  <QuotationsPage />
                </RequirePermission>
              }
            />
            <Route
              path="/billing"
              element={
                <RequirePermission permission={PERMS.ORG_MANAGE}>
                  <BillingPage />
                </RequirePermission>
              }
            />
            <Route
              path="/shift"
              element={
                <RequirePermission permission={PERMS.SHIFT_MANAGE}>
                  <ShiftPage />
                </RequirePermission>
              }
            />
            <Route
              path="/products"
              element={
                <RequirePermission permission={PERMS.CATALOG_VIEW}>
                  <ProductsPage />
                </RequirePermission>
              }
            />
            <Route
              path="/customers"
              element={
                <RequirePermission permission={PERMS.PARTY_MANAGE}>
                  <CustomersPage />
                </RequirePermission>
              }
            />
            <Route
              path="/suppliers"
              element={
                <RequirePermission permission={PERMS.PARTY_MANAGE}>
                  <SuppliersPage />
                </RequirePermission>
              }
            />
            <Route
              path="/purchasing"
              element={
                <RequirePermission permission={[PERMS.PURCHASE_CREATE, PERMS.PURCHASE_RECEIVE]}>
                  <PurchasingPage />
                </RequirePermission>
              }
            />
            <Route
              path="/stock-transfer"
              element={
                <RequirePermission permission={PERMS.INVENTORY_VIEW}>
                  <StockTransferPage />
                </RequirePermission>
              }
            />
            <Route
              path="/staff"
              element={
                <RequirePermission permission={PERMS.USERS_MANAGE}>
                  <StaffPage />
                </RequirePermission>
              }
            />
            <Route
              path="/roles"
              element={
                <RequirePermission permission={PERMS.ROLES_MANAGE}>
                  <RolesPage />
                </RequirePermission>
              }
            />
            <Route
              path="/branches"
              element={
                <RequirePermission permission={PERMS.ORG_MANAGE}>
                  <BranchesPage />
                </RequirePermission>
              }
            />
            <Route
              path="/audit-log"
              element={
                <RequirePermission permission={PERMS.ORG_MANAGE}>
                  <AuditLogPage />
                </RequirePermission>
              }
            />
            <Route
              path="/sync"
              element={
                <RequirePermission permission={PERMS.SYNC_MANAGE}>
                  <SyncDashboardPage />
                </RequirePermission>
              }
            />
            <Route
              path="/reports"
              element={
                <RequirePermission permission={PERMS.REPORTS_VIEW}>
                  <ReportsPage />
                </RequirePermission>
              }
            />
            <Route
              path="/sales-history"
              element={
                <RequirePermission permission={PERMS.REPORTS_VIEW}>
                  <SalesHistoryPage />
                </RequirePermission>
              }
            />
            <Route
              path="/stock"
              element={
                <RequirePermission permission={PERMS.INVENTORY_VIEW}>
                  <StockPage />
                </RequirePermission>
              }
            />
            <Route
              path="/offers"
              element={
                <RequirePermission permission={PERMS.CATALOG_MANAGE}>
                  <OffersPage />
                </RequirePermission>
              }
            />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<HomeRedirect />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}