(function () {
  const localDate = date => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const displayDate = value => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  });

  class DateRangePicker {
    constructor(options) {
      this.mount = typeof options.mount === "string" ? document.querySelector(options.mount) : options.mount;
      if (!this.mount) throw new Error("Date range picker mount element was not found.");
      this.onApply = options.onApply || (() => {});
      this.onToday = options.onToday || this.onApply;
      const today = localDate(new Date());
      this.fromDate = options.fromDate || today;
      this.toDate = options.toDate || this.fromDate;
      this.pickerStart = "";
      this.pickerEnd = "";
      this.leftMonth = new Date();
      this.render();
      this.bind();
      this.setRange(this.fromDate, this.toDate);
    }

    render() {
      this.mount.classList.add("date-range-picker");
      this.mount.innerHTML = `<input data-role="from" type="hidden"><input data-role="to" type="hidden"><button class="date-range-picker__trigger" data-role="trigger" type="button" aria-haspopup="dialog" aria-expanded="false"><span class="date-range-picker__icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18"></path><path d="M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01"></path></svg></span><span data-role="rangeText">Select date range</span></button><button class="ghost" data-role="today" type="button">Today</button><div class="date-range-picker__popover" data-role="popover" role="dialog" aria-label="Select date range" hidden><div class="date-range-picker__calendars"><div class="date-range-picker__calendar" data-role="leftCalendar"></div><div class="date-range-picker__calendar" data-role="rightCalendar"></div></div><div class="date-range-picker__footer"><span class="date-range-picker__selection" data-role="selection"></span><button class="ghost" data-role="cancel" type="button">Cancel</button><button class="primary" data-role="apply" type="button">Apply Range</button></div></div>`;
      this.elements = Object.fromEntries([...this.mount.querySelectorAll("[data-role]")].map(element => [element.dataset.role, element]));
    }

    bind() {
      this.elements.trigger.onclick = () => this.elements.popover.hidden ? this.open() : this.close();
      this.elements.cancel.onclick = () => this.close();
      this.elements.apply.onclick = () => this.apply();
      this.elements.today.onclick = () => {
        const today = localDate(new Date());
        this.setRange(today, today);
        this.close();
        this.onToday(this.getRange());
      };
      this.elements.popover.onclick = event => event.stopPropagation();
      document.addEventListener("keydown", event => { if (event.key === "Escape") this.close(); });
      document.addEventListener("click", event => {
        if (!this.elements.popover.hidden && !this.mount.contains(event.target)) this.close();
      });
    }

    setRange(fromDate, toDate = fromDate) {
      this.fromDate = fromDate;
      this.toDate = toDate;
      this.elements.from.value = fromDate;
      this.elements.to.value = toDate;
      this.elements.rangeText.textContent = `${displayDate(fromDate)}  –  ${displayDate(toDate)}`;
    }

    getRange() { return { fromDate: this.fromDate, toDate: this.toDate }; }

    open() {
      this.pickerStart = this.fromDate;
      this.pickerEnd = this.toDate;
      const start = new Date(`${this.pickerStart}T12:00:00`);
      this.leftMonth = new Date(start.getFullYear(), start.getMonth(), 1);
      this.renderCalendars();
      this.elements.popover.hidden = false;
      this.elements.trigger.setAttribute("aria-expanded", "true");
    }

    close() {
      this.elements.popover.hidden = true;
      this.elements.trigger.setAttribute("aria-expanded", "false");
    }

    apply() {
      if (!this.pickerStart) return;
      if (!this.pickerEnd) this.pickerEnd = this.pickerStart;
      this.setRange(this.pickerStart, this.pickerEnd);
      this.close();
      this.onApply(this.getRange());
    }

    selectDate(value) {
      if (!this.pickerStart || this.pickerEnd) {
        this.pickerStart = value;
        this.pickerEnd = "";
      } else if (value < this.pickerStart) {
        this.pickerEnd = this.pickerStart;
        this.pickerStart = value;
      } else {
        this.pickerEnd = value;
      }
      this.renderCalendars();
    }

    renderCalendars() {
      this.renderCalendar(this.elements.leftCalendar, this.leftMonth, "left");
      this.renderCalendar(this.elements.rightCalendar, new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + 1, 1), "right");
      this.elements.selection.textContent = this.pickerStart
        ? (this.pickerEnd ? `${displayDate(this.pickerStart)} – ${displayDate(this.pickerEnd)}` : `Start: ${displayDate(this.pickerStart)} · select an end date`)
        : "Select a start date";
    }

    renderCalendar(root, month, side) {
      const year = month.getFullYear();
      const monthIndex = month.getMonth();
      const first = new Date(year, monthIndex, 1);
      const gridStart = new Date(year, monthIndex, 1 - first.getDay());
      const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      let days = "";
      for (let index = 0; index < 42; index += 1) {
        const date = new Date(gridStart);
        date.setDate(gridStart.getDate() + index);
        const value = localDate(date);
        const classes = ["date-range-picker__day"];
        if (date.getMonth() !== monthIndex) classes.push("is-outside");
        if (this.pickerStart && this.pickerEnd && value > this.pickerStart && value < this.pickerEnd) classes.push("is-in-range");
        if (value === this.pickerStart) classes.push("is-start");
        if (value === this.pickerEnd) classes.push("is-end");
        days += `<button type="button" class="${classes.join(" ")}" data-date="${value}">${date.getDate()}</button>`;
      }
      root.innerHTML = `<div class="date-range-picker__head"><button type="button" class="date-range-picker__nav" data-move="${side === "left" ? -1 : 0}">${side === "left" ? "◀" : ""}</button><strong>${month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong><button type="button" class="date-range-picker__nav" data-move="${side === "right" ? 1 : 0}">${side === "right" ? "▶" : ""}</button></div><div class="date-range-picker__weekdays">${weekdays.map(day => `<span>${day}</span>`).join("")}</div><div class="date-range-picker__days">${days}</div>`;
      root.querySelectorAll("[data-date]").forEach(button => { button.onclick = () => this.selectDate(button.dataset.date); });
      root.querySelectorAll("[data-move]").forEach(button => {
        button.onclick = () => {
          const move = Number(button.dataset.move);
          if (!move) return;
          this.leftMonth = new Date(this.leftMonth.getFullYear(), this.leftMonth.getMonth() + move, 1);
          this.renderCalendars();
        };
      });
    }
  }

  window.KayDateRangePicker = DateRangePicker;
})();
