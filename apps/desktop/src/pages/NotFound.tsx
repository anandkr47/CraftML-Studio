import { FiAlertCircle } from "react-icons/fi";
import { useNavigate } from "react-router-dom";

const NotFound = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-red-50 to-blue-100">
      <div className="bg-white rounded-2xl shadow-xl p-10 flex flex-col items-center border border-red-200">
        <FiAlertCircle size={48} className="text-red-500 mb-4" />
        <h1 className="text-4xl font-extrabold text-red-700 mb-2">404 - Page Not Found</h1>
        <p className="text-lg text-gray-700 mb-6">The page you are looking for does not exist.</p>
        <button
          className="bg-blue-600 text-white px-6 py-2 rounded-xl shadow hover:bg-blue-700 transition font-semibold text-lg"
          onClick={() => navigate("/")}
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
};
export default NotFound;
