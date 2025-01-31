async function initMap() {
  try {
    const response = await fetch("public/isbn-viewer-style.json")
    const style = await response.json()

    const mapOptions = {
      container: "map",
      style: style,
      attributionControl: false,
      maxZoom: 12.5,
      bounds: [
        [-95.0, 40.97989806962013],
        [99.32, -42.59036211036585],
      ],
      center: [2.1599999999999966, -1.0799360506437938],
      zoom: 2.7,
      renderWorldCopies: false,
      pitchWithRotate: true,
      dragRotate: false,
      keyboard: {
        rotate: false,
      },
    }

    map = new maplibregl.Map(mapOptions)
    map.getCanvas().style.cursor = "crosshair"
    map.touchZoomRotate.disableRotation()

    popup = new maplibregl.Popup({
      className: "hover-popup",
      offset: 10,
      closeButton: false,
      closeOnClick: false,
    })

    clickPopup = new maplibregl.Popup({
      className: "click-popup",
      offset: 10,
      closeButton: true,
      closeOnClick: false,
    })
    clickPopup.on("close", () => {
      clickPopupOpen = false
      if (selectedExtrusionId) deselectExtrusion()
    })

    map.getCanvas().addEventListener("contextmenu", (e) => e.stopPropagation(), true)

    map.on("zoom", () => {
      if (map.getZoom() < 6) {
        popup.remove()
      }
    })

    map.on("mousemove", (e) => {
      if (map.getZoom() < 6) {
        popup.remove()
        return
      }

      if (clickPopupOpen) return

      let popupHTML
      const coordinates = e.lngLat

      if ("holding-extrusion" in featureState && featureState["holding-extrusion"]) {
        const isbnPosition = `${978000000000 + featureState["holding-extrusion"].id}`
        let holdingCount = heightToHoldingCount(featureState["holding-extrusion"].properties.height)
        popupHTML = `ISBN ${isbnPosition}${isbn13Checksum(isbnPosition)}<br>Holding Count: ${holdingCount}`
      } else {
        let [x, y] = lngLatToXY(coordinates.lng, coordinates.lat)
        if (x < 0 || x > 65536) {
          popup.remove()
          return
        }
        if (y < 0 || y > 32768) {
          popup.remove()
          return
        }
        x = Math.trunc(x)
        y = Math.trunc(y)
        popupHTML = `ISBN ${xyToIsbn(x, y)}`
      }
      popup.setLngLat(coordinates).setHTML(popupHTML).addTo(map)
    })

    let hoverLayerEffects = {
      "country-2-fill": {
        minZoom: 2.5,
        propertyName: "language",
        targetLayers: [
          { source: "country_2", sourceLayer: "country_2" },
          { source: "country_2", sourceLayer: "country_2_labels" },
        ],
      },
      "country-3-fill": {
        minZoom: 3.2,
        targetLayers: [
          { source: "country_3", sourceLayer: "country_3" },
          { source: "country_3", sourceLayer: "country_3_labels" },
        ],
      },
      "country-4-fill": {
        minZoom: 5.2,
        targetLayers: [
          { source: "country_4", sourceLayer: "country_4" },
          { source: "country_4", sourceLayer: "country_4_labels" },
        ],
      },
      "country-5-fill": {
        minZoom: 6,
        targetLayers: [
          { source: "country_5", sourceLayer: "country_5" },
          { source: "country_5", sourceLayer: "country_5_labels" },
        ],
      },
      "group-3-fill": {
        minZoom: 3.2,
        targetLayers: [
          { source: "groups", sourceLayer: "groups_3" },
          { source: "groups", sourceLayer: "groups_labels_3" },
        ],
      },
      "group-4-fill": {
        minZoom: 5.2,
        targetLayers: [
          { source: "groups4", sourceLayer: "groups_4" },
          { source: "groups4", sourceLayer: "groups_labels_4" },
        ],
      },
      "group-5-fill": {
        minZoom: 6,
        targetLayers: [
          { source: "groups5", sourceLayer: "groups_5" },
          { source: "groups5", sourceLayer: "groups_labels_5" },
        ],
      },
      "group-6-fill": {
        minZoom: 8,
        targetLayers: [
          { source: "groups6", sourceLayer: "groups_6" },
          { source: "groups6", sourceLayer: "groups_labels_6" },
        ],
      },
      "group-7-fill": {
        minZoom: 9,
        targetLayers: [
          { source: "groups7", sourceLayer: "groups_7" },
          { source: "groups7", sourceLayer: "groups_labels_7" },
        ],
      },
      "holding-extrusion": {
        minZoom: 8,
        targetLayers: [{ source: "extrusions", sourceLayer: "holdings" }],
      },
    }

    function addMouseMoveListeners(map, hoverLayerEffects) {
      for (const [layerId, config] of Object.entries(hoverLayerEffects)) {
        const { minZoom, targetLayers } = config

        map.on("mousemove", layerId, (e) => {
          if (map.getZoom() < minZoom) return

          if (e.features.length > 0) {
            const hoveredFeature = e.features[0]
            const hoveredFeatureId = hoveredFeature.id

            if (featureState[layerId] && featureState[layerId].id !== hoveredFeatureId) {
              targetLayers.forEach((layer) => {
                map.setFeatureState(
                  {
                    source: layer.source,
                    sourceLayer: layer.sourceLayer,
                    id: featureState[layerId].id,
                  },
                  { hover: false },
                )
              })
            }
            featureState[layerId] = { id: hoveredFeatureId, properties: hoveredFeature.properties }

            targetLayers.forEach((layer) => {
              map.setFeatureState(
                {
                  source: layer.source,
                  sourceLayer: layer.sourceLayer,
                  id: hoveredFeatureId,
                },
                { hover: true },
              )
            })
          }
        })

        map.on("mouseleave", layerId, () => {
          if (featureState[layerId]) {
            targetLayers.forEach((layer) => {
              map.setFeatureState(
                {
                  source: layer.source,
                  sourceLayer: layer.sourceLayer,
                  id: featureState[layerId].id,
                },
                { hover: false },
              )
            })
            featureState[layerId] = null
          }
        })

        map.on("zoom", () => {
          if (map.getZoom() < minZoom && featureState[layerId]) {
            targetLayers.forEach((layer) => {
              map.setFeatureState(
                {
                  source: layer.source,
                  sourceLayer: layer.sourceLayer,
                  id: featureState[layerId].id,
                },
                { hover: false },
              )
            })
            featureState[layerId] = null
          }
        })
      }
    }

    addMouseMoveListeners(map, hoverLayerEffects)

    map.on("click", (e) => {
      if (map.getZoom() < 6) {
        return
      }
      const coordinates = e.lngLat

      if ("holding-extrusion" in featureState && featureState["holding-extrusion"]) {
        const isbnPosition = `${978000000000 + featureState["holding-extrusion"].id}`
        const isbn = `${isbnPosition}${isbn13Checksum(isbnPosition)}`
        const holdingCount = heightToHoldingCount(
          featureState["holding-extrusion"].properties.height,
        )
        const [x, y] = isbnToXY(isbn)
        const [lng0, lat0] = xyToLngLat(x, y)
        const [lng1, lat1] = xyToLngLat(x + 1, y + 1)
        addClickPopup(lng0 + (lng1 - lng0) / 2, lat0 + (lat1 - lat0) / 2, isbn, holdingCount)

        map.setLayoutProperty("hover-rectangle", "visibility", "none")

        if (selectedExtrusionId && selectedExtrusionId != featureState["holding-extrusion"].id) {
          deselectExtrusion()
        }

        map.setFeatureState(
          {
            source: "extrusions",
            sourceLayer: "holdings",
            id: featureState["holding-extrusion"].id,
          },
          { selected: true },
        )
        selectedExtrusionId = featureState["holding-extrusion"].id
      } else {
        let [x, y] = lngLatToXY(coordinates.lng, coordinates.lat)
        
        if (x < 0 || x > 65536) {
          return
        }
        if (y < 0 || y > 32768) {
          return
        }

        x = Math.trunc(x)
        y = Math.trunc(y)
        const [lng0, lat0] = xyToLngLat(x, y)
        const [lng1, lat1] = xyToLngLat(x + 1, y + 1)
        highlightRectangle(lng0, lng0 + (lng1 - lng0), lat0, lat0 + (lat1 - lat0))
        addClickPopup(lng0 + (lng1 - lng0) / 2, lat0, xyToIsbn(x, y))
      }
    })
  } catch (error) {
    console.error("Error loading the style:", error)
  }
}

function isbnToXY(isbn) {
  let isbnWithoutChecksum = Number(isbn.slice(0, -1))
  let position = isbnWithoutChecksum - 978000000000
  let xy = hilbertCurve.indexToPoint(position, 15)

  if (position > 1073741824) {
    xy.x += 32768
  }
  return [xy.x, xy.y]
}

function xyToLngLat(x, y) {
  let lng = (x * 360) / (128 * tileSize) + ((upperLeftTileX / Math.pow(2, 7)) * 360 - 180)
  let lat =
    (180 / Math.PI) *
    Math.atan(Math.sinh(Math.PI * (1 - (2 * (upperLeftTileY + y / tileSize)) / Math.pow(2, 7))))
  return [lng, lat]
}

function lngLatToXY(lng, lat) {
  let x = ((lng - ((upperLeftTileX / Math.pow(2, 7)) * 360 - 180)) * (128 * tileSize)) / 360
  const latRad = (lat * Math.PI) / 180
  const sinhValue = Math.tan(latRad)
  const innerValue = Math.asinh(sinhValue)
  let y = (((1 - innerValue / Math.PI) * Math.pow(2, 7)) / 2) * tileSize - upperLeftTileY * tileSize
  return [x, y]
}

function xyToIsbn(x, y) {
  let position = hilbertCurve.pointToIndex({ x: x, y: y }, 15)
  if (x >= 32768) {
    position += 1073741824
  }
  let isbn = `${978000000000 + position}`
  return `${isbn}${isbn13Checksum(isbn)}`
}

function inverseLatToY(lat) {
  const latRad = (lat * Math.PI) / 180
  const sinhValue = Math.tan(latRad)
  const innerValue = Math.asinh(sinhValue)
  return (((1 - innerValue / Math.PI) * Math.pow(2, 7)) / 2) * 1000 - 48 * 1000
}

function isbn13Checksum(isbn) {
  let sum = 0
  for (let [index, digit] of isbn.split("").entries()) {
    if ((index + 1) % 2 == 0) {
      sum += parseInt(digit) * 3
    } else {
      sum += parseInt(digit)
    }
  }
  let checksum = 10 - (sum % 10)
  if (checksum == 10) {
    return 0
  } else {
    return checksum
  }
}

function heightToHoldingCount(height) {
  let holdingCount = -Math.log(height / 3000) / 0.8
  return Math.round(holdingCount)
}

function highlightRectangle(lngStart, lngEnd, latStart, latEnd) {
  const rectangle = {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [lngStart, latStart],
          [lngEnd, latStart],
          [lngEnd, latEnd],
          [lngStart, latEnd],
          [lngStart, latStart],
        ],
      ],
    },
  }

  map.getSource("hover-rectangle").setData({
    type: "FeatureCollection",
    features: [rectangle],
  })
  map.setLayoutProperty("hover-rectangle", "visibility", "visible")
}

function addClickPopup(lng, lat, isbn, holdingCount) {
  clickPopup.remove()
  popup.remove()
  let content = `ISBN ${isbn}`
  if (holdingCount != null) {
    content += `<br>Holding count: ${holdingCount}`
  }
  content += `<br><a id="search-button" target="_blank" href="https://annas-archive.org/search?q=${isbn}">Open in Search</a>`
  clickPopup.setLngLat({ lng: lng, lat: lat }).setHTML(content).addTo(map)
  clickPopupOpen = true

  // Prevent popup from blocking hover effects and zooming
  clickPopup._container.addEventListener("mouseenter", (e) => {
    map.getCanvas().dispatchEvent(
      new MouseEvent("mousemove", {
        bubbles: true,
        clientX: e.screenX,
        clientY: e.screenY,
      }),
    )
  })
  clickPopup._container.addEventListener("wheel", (e) => {
    map.getCanvas().dispatchEvent(
      new WheelEvent("wheel", {
        clientX: e.clientX,
        clientY: e.clientY,
        deltaX: e.deltaX,
        deltaY: e.deltaY,
        deltaZ: e.deltaZ,
        deltaMode: e.deltaMode,
        bubbles: true,
      }),
    )
  })
}

function flyToIsbn(isbn) {
  clickPopup.remove()
  const [x, y] = isbnToXY(isbn)
  const [lng0, lat0] = xyToLngLat(x, y)
  const [lng1, lat1] = xyToLngLat(x + 1, y + 1)

  highlightRectangle(lng0, lng0 + (lng1 - lng0), lat0, lat0 + (lat1 - lat0))

  map.flyTo({
    center: [lng0, lat0],
    zoom: 12,
    essential: true,
  })

  let holdingCount
  const lngLat = [lng0, lat0]
  const point = map.project(lngLat)
  const features = map.queryRenderedFeatures(point)
  if (features.length > 0)
    for (const feature of features) {
      console.log(feature.layer["source-layer"])
      if (feature.layer["source-layer"] == "holdings") {
        
        holdingCount = heightToHoldingCount(feature.properties.height)
      }
    }
  map.once("moveend", () => {
    addClickPopup(lng0 + (lng1 - lng0) / 2, lat0, isbn, holdingCount)
  })
}

function toggleRareBookView() {
  const currentMode = map.getLayoutProperty("holding-extrusion", "visibility")

  if (clickPopupOpen) clickPopup.remove()

  if (currentMode == "none") {
    map.dragRotate.enable({ pitchWithRotate: true })
    map.setLayoutProperty("hover-rectangle", "visibility", "none")
    map.setLayoutProperty("holding-extrusion", "visibility", "visible")
    map.setPaintProperty("holding-extrusion", "fill-extrusion-opacity", 1)
    map.flyTo({
      pitch: 55,
      speed: 0.8,
      essential: true,
    })
  } else {
    map.dragRotate.disable()
    if (selectedExtrusionId) deselectExtrusion()
    map.setLayoutProperty("holding-extrusion", "visibility", "none")
    map.setPaintProperty("holding-extrusion", "fill-extrusion-opacity", 0)
    map.setPitch(0).setBearing(0)
  }
}

function deselectExtrusion() {
  map.setFeatureState(
    {
      source: "extrusions",
      sourceLayer: "holdings",
      id: selectedExtrusionId,
    },
    { selected: false },
  )
}

function validateIsbn(isbn) {
  const trimmedValue = isbn.trim()
  if (trimmedValue === "") return false

  if (!/^[1-9]\d{12}$/.test(trimmedValue)) return false

  const lastDigit = trimmedValue.slice(-1)
  const rest = trimmedValue.slice(0, -1)
  return isbn13Checksum(rest) == lastDigit
}

function switchDataset(datasetName) {
  let legend = document.getElementById("legend")
  if (datasetName == "all_isbns") {
    legend.style.display = "block"
  } else {
    legend.style.display = "none"
  }
  map.getSource('isbn-pixel').setUrl(`pmtiles://./public/${datasetName}.pmtiles`)
  map.getSource('extrusions').setUrl(`pmtiles://./public/${datasetName}_holdings.pmtiles`);
}

// Event Listeners:
const rareViewModeButton = document.getElementById("rare-book-view")
rareViewModeButton.addEventListener("click", () => {
  rareViewModeButton.classList.toggle("active")
  toggleRareBookView()
})
rareViewModeButton.addEventListener("mouseenter", () => popup.remove())

const input = document.getElementById("isbn-input")
input.addEventListener("keyup", (e) => {
  if (e.key === "Enter") {
    let isbn = input.value.replace(/-/g, "")
    if (!validateIsbn(isbn)) {
      input.classList.add("invalid")
    } else {
      input.blur()
      flyToIsbn(isbn)
    }
  }
})
input.addEventListener("input", () => input.classList.remove("invalid"))
input.addEventListener("blur", () => input.classList.remove("invalid"))
input.addEventListener("mouseenter", () => popup.remove())

document.getElementById("legend").addEventListener("mouseenter", () => popup.remove())

// Dataset menu:
const datasets = {
  all_isbns: "All ISBNs",
  md5: "Files in Anna’s Archive",
  cadal_ssno: "CADAL SSNOs",
  cerlalc: "CERLALC data leak",
  duxiu_ssid: "DuXiu SSIDs",
  edsebk: "EBSCOhost’s eBook Index",
  gbooks: "Google Books",
  goodreads: "Goodreads",
  ia: "Internet Archive",
  isbndb: "ISBNdb",
  isbngrp: "ISBN Global Register of Publishers",
  libby: "Libby",
  nexusstc: "Nexus/STC",
  oclc: "OCLC/Worldcat",
  ol: "OpenLibrary",
  rgb: "Russian State Library",
  trantor: "Imperial Library of Trantor",
}

const dropdown = document.getElementById("dropdown")
const menuButton = document.getElementById("menu-button")
menuButton.addEventListener("mouseenter", () => popup.remove())
dropdown.addEventListener("mouseenter", () => popup.remove())

for (const [key, value] of Object.entries(datasets)) {
  let item = document.createElement("a")
  item.textContent = value
  item.setAttribute("data-key", key)
  item.addEventListener("click", selectItem)
  if (key == "all_isbns") {
    item.classList.add("selected")
  }
  dropdown.appendChild(item)
}

menuButton.addEventListener("click", () => (dropdown.style.display = "block"))

function selectItem(event) {
  let items = document.querySelectorAll(".menu-content a")
  items.forEach((item) => item.classList.remove("selected"))
  event.target.classList.add("selected")
  dropdown.style.display = "none"
  switchDataset(event.target.dataset.key)
}

document.addEventListener("click", (e) => {
  if (!dropdown.contains(e.target) && !menuButton.contains(e.target))
    dropdown.style.display = "none"
})

let protocol = new pmtiles.Protocol()
maplibregl.addProtocol("pmtiles", protocol.tile)

const tileSize = 1000
const upperLeftTileX = 32
const upperLeftTileY = 48
let map
let popup
let clickPopup
let clickPopupOpen
let featureState = {}
let selectedExtrusionId
initMap()
