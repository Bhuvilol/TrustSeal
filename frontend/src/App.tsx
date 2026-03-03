import { Navigate, Route, Routes } from 'react-router-dom';
import ProtectedRoute from '@/components/ProtectedRoute';
import AppLayout from '@/layouts/AppLayout';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import LandingPage from '@/pages/LandingPage';
import DashboardPage from '@/pages/DashboardPage';
import DevicesPage from '@/pages/DevicesPage';
import ShipmentsPage from '@/pages/ShipmentsPage';
import DeviceDetailsPage from '@/pages/DeviceDetailsPage';
import ShipmentDetailsPage from '@/pages/ShipmentDetailsPage';
import DeviceLogsPage from '@/pages/DeviceLogsPage';
import IntelligencePage from '@/pages/IntelligencePage';
import QRLookupPage from '@/pages/QRLookupPage';
import NotFoundPage from '@/pages/NotFoundPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/home" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/devices/:deviceId" element={<DeviceDetailsPage />} />
          <Route path="/shipments" element={<ShipmentsPage />} />
          <Route path="/shipments/:shipmentId" element={<ShipmentDetailsPage />} />
          <Route path="/device-logs" element={<DeviceLogsPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/device/:deviceId" element={<DeviceDetailsPage />} />
          <Route path="/shipment/:shipmentId" element={<ShipmentDetailsPage />} />
          <Route path="/lookup" element={<QRLookupPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;

