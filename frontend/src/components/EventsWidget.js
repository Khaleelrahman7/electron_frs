import React, { useState } from 'react';
import FaceEvents from './FaceEvents';
import FindOccurrence from './FindOccurrence';
import './EventsWidget.css';

const EventsWidget = () => {
  const [activeTab, setActiveTab] = useState('face-events');

  return (
    <div className="events-widget">
      <div className="events-tabs">
        <button
          className={`tab-button ${activeTab === 'face-events' ? 'active' : ''}`}
          onClick={() => setActiveTab('face-events')}
        >
          Face Events
        </button>
        <button
          className={`tab-button ${activeTab === 'find-occurrence' ? 'active' : ''}`}
          onClick={() => setActiveTab('find-occurrence')}
        >
          Find Occurrence
        </button>
      </div>
      
      <div className="tab-content">
        {activeTab === 'face-events' && <FaceEvents />}
        {activeTab === 'find-occurrence' && <FindOccurrence />}
      </div>
    </div>
  );
};

export default EventsWidget;
