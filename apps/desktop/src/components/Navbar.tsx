import { Link } from "react-router-dom";

const Navbar = () => (
  <nav className="bg-gray-800 text-white p-4 flex gap-4">
    <Link to="/">Dashboard</Link>
    <Link to="/datasets">Datasets</Link>
    <Link to="/crawler">Crawler</Link>
    <Link to="/train">Training</Link>
    <Link to="/compress">Compression</Link>
    <Link to="/deploy">Deployment</Link>
  </nav>
);
export default Navbar;
