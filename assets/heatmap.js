// Rendu heatmap côté client avec Leaflet.heat
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        renderHeatmap: function(data) {
            if (!data || data.length === 0) return [];
            
            return [
                window.L.heatLayer(data, {
                    radius: 25,
                    blur: 15,
                    maxZoom: 10,
                    gradient: {0.4: '#52B788', 0.6: '#F4A620', 0.8: '#E2001A'}
                })
            ];
        }
    }
});