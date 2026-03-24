import React, { useState, useEffect } from 'react';
import { Download, Search, Filter, Calendar, FileText, FileSpreadsheet, Users, UserX, AlertTriangle, Clock, ArrowLeft } from 'lucide-react';
import useAuthStore from '../../store/authStore';
import { API_BASE_URL, getApiUrl, fixImageUrl } from '../../utils/apiConfig';
import './AttendanceReport.css';

const AttendanceReport = ({ reportType, setActiveTab }) => {
    const { user: currentUser, token } = useAuthStore();
    const [reportData, setReportData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [targetDate, setTargetDate] = useState(new Date().toISOString().split('T')[0]);

    // For aggregate reports
    const [startDate, setStartDate] = useState(() => {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        return d.toISOString().split('T')[0];
    });
    const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);

    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('All');

    const isAggregate = reportType === 'week-report' || reportType === 'month-report';

    useEffect(() => {
        const initialFilter = localStorage.getItem('attendanceFilter');
        if (initialFilter) {
            setStatusFilter(initialFilter);
            localStorage.removeItem('attendanceFilter');
        }
    }, [reportType]);

    useEffect(() => {
        if (reportType === 'week-report') {
            const d = new Date();
            d.setDate(d.getDate() - 7);
            setStartDate(d.toISOString().split('T')[0]);
            setEndDate(new Date().toISOString().split('T')[0]);
        } else if (reportType === 'month-report') {
            const d = new Date();
            d.setDate(1);
            setStartDate(d.toISOString().split('T')[0]);
            setEndDate(new Date().toISOString().split('T')[0]);
        }
    }, [reportType]);

    useEffect(() => {
        fetchAttendanceData();
    }, [targetDate, startDate, endDate, reportType]);

    const fetchAttendanceData = async () => {
        try {
            setLoading(true);
            setError(null);

            const url = isAggregate
                ? `${API_BASE_URL}/api/events/attendance/aggregate?start_date=${startDate}&end_date=${endDate}`
                : `${API_BASE_URL}/api/events/attendance?target_date=${targetDate}`;

            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch attendance data: ${response.statusText}`);
            }

            const data = await response.json();
            setReportData(data.attendance || data.aggregate || []);
        } catch (err) {
            console.error("Error fetching attendance:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const getDayTitle = () => {
        switch (reportType) {
            case 'week-report': return 'Weekly Known Face Report';
            case 'month-report': return 'Monthly Known Face Report';
            default: return 'Known Face Report';
        }
    };

    const filteredData = reportData.filter(record => {
        const matchesSearch = record.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (record.emp_id && record.emp_id.toLowerCase().includes(searchTerm.toLowerCase()));

        let matchesStatus = true;
        if (statusFilter === 'Present' || statusFilter === 'Recognized') {
            matchesStatus = isAggregate ? (record.total_recognitions || 0) > 0 : (record.status === 'Present' || record.status === 'Recognized');
        }

        return matchesSearch && matchesStatus;
    });

    // Summary calculations
    const totalRecognized = isAggregate ? reportData.reduce((acc, r) => acc + (r.total_recognitions || 0), 0) : reportData.length;

    const exportToCSV = () => {
        if (filteredData.length === 0) return;

        const headers = isAggregate
            ? ['S.No', 'Criminal ID', 'Name', 'Category', 'Total Recognitions']
            : ['S.No', 'Criminal ID', 'Name', 'Category', 'Recognition Time'];

        const csvRows = [headers.join(',')];

        filteredData.forEach(row => {
            const values = [
                row.s_no || '',
                `"${row.emp_id || ''}"`,
                `"${row.name || ''}"`,
                `"${row.category || 'Criminal'}"`
            ];

            if (isAggregate) {
                values.push(row.total_recognitions || 0);
            } else {
                values.push(row.punch_in || row.timestamp || '-');
            }

            csvRows.push(values.join(','));
        });

        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', `${getDayTitle().replace(/\s+/g, '_')}.csv`);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const exportToPDF = async () => {
        try {
            setLoading(true);
            // Construct the appropriate URL based on report type
            const endpoint = isAggregate
                ? `${API_BASE_URL}/api/events/export/attendance-aggregate-pdf?start_date=${startDate}&end_date=${endDate}`
                : `${API_BASE_URL}/api/events/export/attendance-pdf?target_date=${targetDate}`;

            const response = await fetch(endpoint, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to generate PDF');
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;

            const filename = isAggregate
                ? `recognition_report_${startDate}_to_${endDate}.pdf`
                : `recognition_report_${targetDate}.pdf`;

            a.download = filename;
            document.body.appendChild(a);
            a.click();

            // Cleanup
            setTimeout(() => {
                window.URL.revokeObjectURL(downloadUrl);
                document.body.removeChild(a);
            }, 100);
        } catch (err) {
            console.error("Error exporting PDF:", err);
            setError(`Failed to export PDF: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="attendance-report-container animate-fade-in">
            <div className="report-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {setActiveTab && (
                        <button
                            onClick={() => setActiveTab('dashboard')}
                            className="btn-back-clean"
                            style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-secondary)' }}
                        >
                            <ArrowLeft size={20} /> Back
                        </button>
                    )}
                    <div>
                        <h2 style={{ margin: 0 }}>{getDayTitle()}</h2>
                        <p className="subtitle" style={{ margin: '4px 0 0' }}>View and manage known face recognition logs</p>
                    </div>
                </div>
                <div className="report-actions">
                    <div className="search-bar">
                        <Search size={18} />
                        <input
                            type="text"
                            placeholder="Search by ID or Name"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <div className="status-filter" style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-input)', padding: '0 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <Filter size={18} style={{ color: 'var(--text-secondary)', marginRight: '8px' }} />
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', padding: '8px 0', outline: 'none', cursor: 'pointer' }}
                        >
                            <option value="All">All Categories</option>
                            <option value="Recognized">Recognized</option>
                        </select>
                    </div>

                    {isAggregate ? (
                        <div className="date-picker-wrap" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <Calendar size={18} />
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="date-input"
                            />
                            <span style={{ color: 'var(--text-secondary)' }}>to</span>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="date-input"
                            />
                        </div>
                    ) : (
                        <div className="date-picker-wrap">
                            <Calendar size={18} />
                            <input
                                type="date"
                                value={targetDate}
                                onChange={(e) => setTargetDate(e.target.value)}
                                className="date-input"
                            />
                        </div>
                    )}

                    <div className="export-buttons" style={{ display: 'flex', gap: '8px' }}>
                        <button className="btn-export" onClick={exportToCSV} title="Export as Excel/CSV">
                            <FileSpreadsheet size={18} /> CSV
                        </button>
                        <button className="btn-export pdf-btn" onClick={exportToPDF} title="Export as PDF">
                            <FileText size={18} /> PDF
                        </button>
                    </div>
                </div>
            </div>

            {/* Summary Bar */}
            <div className="summary-bar" style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
                <div className="summary-card" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', background: 'rgba(16,185,129,0.1)', borderRadius: '8px', color: '#10b981' }}>
                    <Users size={18} /> <strong>{totalRecognized}</strong> Recognitions
                </div>
                <div className="summary-card" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', background: 'rgba(59,130,246,0.1)', borderRadius: '8px', color: '#3b82f6' }}>
                    <Clock size={18} /> <strong>{isAggregate ? filteredData.length : reportData.length}</strong> Profiles
                </div>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                </div>
            )}

            <div className="table-container">
                {loading ? (
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>Loading recognition records...</p>
                    </div>
                ) : (
                    <table className="attendance-table">
                        <thead>
                            <tr>
                                <th>S.No</th>
                                <th>Criminal ID</th>
                                <th>Name</th>
                                <th>Category</th>
                                {isAggregate ? (
                                    <th>Total Recognitions</th>
                                ) : (
                                    <th>Recognition Time</th>
                                )}
                            </tr>
                        </thead>
                        <tbody>
                            {filteredData.length > 0 ? (
                                filteredData.map((record, index) => (
                                    <tr key={record.emp_id || index}>
                                        <td>{record.s_no}</td>
                                        <td className="emp-id">{record.emp_id || '-'}</td>
                                        <td>
                                            <div className="name-cell">
                                                {record.photo_path ? (
                                                    <img
                                                        src={fixImageUrl(record.photo_path)}
                                                        alt={record.name}
                                                        className="mini-avatar"
                                                        onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
                                                    />
                                                ) : null}
                                                <div
                                                    className="mini-avatar-placeholder"
                                                    style={{ display: record.photo_path ? 'none' : 'flex' }}
                                                >
                                                    {record.name ? record.name.charAt(0).toUpperCase() : (record.email ? record.email.charAt(0).toUpperCase() : 'U')}
                                                </div>
                                                <span>{record.name}</span>
                                            </div>
                                        </td>
                                        <td>{record.category || 'Criminal'}</td>
                                        {isAggregate ? (
                                            <td style={{ color: '#10b981', fontWeight: 'bold' }}>{record.total_recognitions || 0}</td>
                                        ) : (
                                            <td className="time-cell">{record.punch_in || record.timestamp || '-'}</td>
                                        )}
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={isAggregate ? "10" : "10"} className="no-data">
                                        No recognition records found for this {isAggregate ? 'date range' : 'date'}.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default AttendanceReport;
