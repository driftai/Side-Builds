import { css, html, LitElement, svg, CSSResultGroup } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { CircularButton } from '../CircularButton-Component/CircularButton.js';

// VolumeButton component
// -----------------------------------------------------------------------------
@customElement('volume-button')
export class VolumeButton extends CircularButton {
  @property({ type: Number }) value = 1; // Default volume 100%

  private dragStartPos = 0;
  private dragStartValue = 0;

  constructor() {
    super();
    this.handlePointerDown = this.handlePointerDown.bind(this);
    this.handlePointerMove = this.handlePointerMove.bind(this);
    this.handlePointerUp = this.handlePointerUp.bind(this);
    this.handleWheel = this.handleWheel.bind(this);
  }

  private handlePointerDown(e: PointerEvent) {
    // Stop propagation to prevent other interactions like play/pause if overlapping
    e.stopPropagation();
    this.dragStartPos = e.clientY;
    this.dragStartValue = this.value;
    document.body.classList.add('dragging-volume'); // Use a different class to avoid conflicts
    window.addEventListener('pointermove', this.handlePointerMove);
    window.addEventListener('pointerup', this.handlePointerUp);
    this.dispatchEvent(new CustomEvent('dragstart'));
  }

  private handlePointerMove(e: PointerEvent) {
    e.stopPropagation();
    const delta = this.dragStartPos - e.clientY;
    let newValue = this.dragStartValue + delta * 0.01; // Adjust sensitivity as needed
    newValue = Math.max(0, Math.min(1, newValue)); // Clamp between 0 and 1
    if (this.value !== newValue) {
      this.value = newValue;
      console.log('VolumeButton: Dispatching volume change:', this.value);
      this.dispatchEvent(new CustomEvent<number>('input', { detail: this.value }));
    }
  }

  private handlePointerUp(e: PointerEvent) {
    e.stopPropagation();
    window.removeEventListener('pointermove', this.handlePointerMove);
    window.removeEventListener('pointerup', this.handlePointerUp);
    document.body.classList.remove('dragging-volume');
    this.dispatchEvent(new CustomEvent('dragend'));
  }

  private handleWheel(e: WheelEvent) {
    e.stopPropagation();
    e.preventDefault(); // Prevent page scroll
    const delta = e.deltaY;
    let newValue = this.value + delta * -0.001; // Adjust sensitivity as needed
    newValue = Math.max(0, Math.min(1, newValue)); // Clamp between 0 and 1
    if (this.value !== newValue) {
      this.value = newValue;
      console.log('VolumeButton: Dispatching volume change (wheel):', this.value);
      this.dispatchEvent(new CustomEvent<number>('input', { detail: this.value }));
    }
  }

  // For simplicity, this icon won't show fill level, just rotation.
  protected override renderIcon() {
    const volume = this.value; // 0 to 1

    // Static Speaker Icon parts
    const speakerBodyPath = "M60 45 H65 L75 35 V73 L65 63 H60 V45 Z";
    const wave1Path = "M80 45 V63 C83 60 83 48 80 45 Z";
    const wave2Path = "M85 42 V66 C90 62 90 46 85 42 Z";

    let wave1Svg = svg``;
    let wave2Svg = svg``;

    // Apply centering transform to speaker parts
    const speakerTransform = "translate(2.5,0)";

    if (volume > 0 && volume <= 0.5) {
      wave1Svg = svg`<path d="${wave1Path}" fill="#FEFEFE" transform="${speakerTransform}"/>`;
    } else if (volume > 0.5) {
      wave1Svg = svg`<path d="${wave1Path}" fill="#FEFEFE" transform="${speakerTransform}"/>`;
      wave2Svg = svg`<path d="${wave2Path}" fill="#FEFEFE" transform="${speakerTransform}"/>`;
    }

    const speakerGroup = svg`
      <g>
        <path d="${speakerBodyPath}" fill="#FEFEFE" transform="${speakerTransform}"/>
        ${wave1Svg}
        ${wave2Svg}
      </g>
    `;

    // Arc and Dot parts
    const arcRadius = 38; 
    const iconCenterX = 70;
    const iconCenterY = 54;

    const rotationRangeRad = Math.PI * 2 * 0.75; // 270 degrees of arc
    const minAngleRad = -rotationRangeRad / 2 - Math.PI / 2; // Start angle: -1.25 * PI (-225 deg)
    const maxAngleRad = rotationRangeRad / 2 - Math.PI / 2;   // End angle: 0.25 * PI (45 deg)
    
    const currentAngleRad = minAngleRad + volume * (maxAngleRad - minAngleRad);
    const dotRotationDeg = currentAngleRad * (180 / Math.PI);

    const arcAndDotGroup = svg`
      <g>
        <!-- Arc Track -->
        <path
          d=${this.describeArc(iconCenterX, iconCenterY, minAngleRad, maxAngleRad, arcRadius)}
          fill="none"
          stroke="#000000"
          stroke-opacity="0.2"
          stroke-width="3"
          stroke-linecap="round" />
        <!-- Filled Arc -->
        <path
          d=${this.describeArc(iconCenterX, iconCenterY, minAngleRad, currentAngleRad, arcRadius)}
          fill="none"
          stroke="#FEFEFE"
          stroke-opacity="0.7"
          stroke-width="3"
          stroke-linecap="round" />
        <!-- Dot -->
        <g transform="translate(${iconCenterX}, ${iconCenterY}) rotate(${dotRotationDeg})">
          <circle cx="${arcRadius}" cy="0" r="3.5" fill="#FEFEFE" />
        </g>
      </g>
    `;
    // Render arc/dot group first, so speaker icon is visually on top/in the center.
    return svg`${arcAndDotGroup}${speakerGroup}`;
  }

  // Helper method to describe an SVG arc path
  private describeArc(
    centerX: number,
    centerY: number,
    startAngle: number, // in radians
    endAngle: number,   // in radians
    radius: number,
  ): string {
    const startX = centerX + radius * Math.cos(startAngle);
    const startY = centerY + radius * Math.sin(startAngle);
    const endX = centerX + radius * Math.cos(endAngle);
    const endY = centerY + radius * Math.sin(endAngle);

    const angleDiff = endAngle - startAngle;
    // Ensure angleDiff is in (-2PI, 2PI) for largeArcFlag logic
    const normalizedAngleDiff = angleDiff % (2 * Math.PI);

    const largeArcFlag = normalizedAngleDiff > Math.PI ? '1' : '0';
    
    // If start and end are the same (or very close for a full circle segment which isn't the case here for the track itself)
    // and we want to draw a tiny segment, this might need adjustment. But for our use, it should be fine.
    // The sweep flag '1' means positive angle direction (CCW for standard SVG geometry)
    return (
      `M ${startX} ${startY}` +
      `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY}`
    );
  }

  override render() {
    // Add event listeners directly to the hitbox for this button
    return html`${this.renderSVG()}
      <div 
        class="hitbox"
        @pointerdown=${this.handlePointerDown}
        @wheel=${this.handleWheel}
      ></div>`;
  }
} 