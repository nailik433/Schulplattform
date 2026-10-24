/* Shared behaviour: large drop areas and small prompt-based actions. */
(function () {
    function size(n) {
        return n < 1048576 ? Math.max(1, Math.round(n / 1024)) + ' KB' : (n / 1048576).toFixed(1).replace('.', ',') + ' MB';
    }

    // ---- Large drag & drop areas (<label class="dropzone dropzone-lg js-dropzone">) ----
    function initDropzone(zone) {
        var input = zone.querySelector('input[type=file]');
        var list = zone.querySelector('.dz-list');
        var form = zone.closest('form');
        var btn = form && form.querySelector('button[type=submit]');
        if (!input || !list || !btn) { return; }

        function render() {
            list.innerHTML = '';
            Array.prototype.forEach.call(input.files, function (f) {
                var li = document.createElement('li');
                li.textContent = '📄 ' + f.name;
                var s = document.createElement('span');
                s.className = 'dz-size';
                s.textContent = size(f.size);
                li.appendChild(s);
                list.appendChild(li);
            });
            zone.classList.toggle('has-files', input.files.length > 0);
            btn.disabled = input.files.length === 0;
        }
        function addFiles(files) {
            if (!window.DataTransfer) { return; }   // fallback: the native input still works
            var dt = new DataTransfer();
            Array.prototype.forEach.call(input.files, function (f) { dt.items.add(f); });
            Array.prototype.forEach.call(files, function (f) { dt.items.add(f); });
            input.files = dt.files;
            render();
        }

        input.addEventListener('change', render);
        ['dragenter', 'dragover'].forEach(function (ev) {
            zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add('drag'); });
        });
        zone.addEventListener('dragleave', function (e) {
            if (!zone.contains(e.relatedTarget)) { zone.classList.remove('drag'); }
        });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('drag');
            if (e.dataTransfer && e.dataTransfer.files.length) { addFiles(e.dataTransfer.files); }
        });
        form.addEventListener('submit', function () {
            btn.textContent = 'Wird hochgeladen …';
            setTimeout(function () { btn.disabled = true; }, 0);   // after the browser has read the form
        });
        render();
    }

    // ---- Ask for a text and POST it (rename actions) ----
    window.spPrompt = function (url, message, current, field) {
        var value = window.prompt(message, current || '');
        if (value === null) { return; }
        var token = document.querySelector('input[name=csrfmiddlewaretoken]');
        var form = document.createElement('form');
        form.method = 'post';
        form.action = url;
        var csrf = document.createElement('input');
        csrf.type = 'hidden'; csrf.name = 'csrfmiddlewaretoken'; csrf.value = token ? token.value : '';
        var input = document.createElement('input');
        input.type = 'hidden'; input.name = field || 'name'; input.value = value;
        form.appendChild(csrf);
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    };

    document.querySelectorAll('.js-dropzone').forEach(initDropzone);
})();
