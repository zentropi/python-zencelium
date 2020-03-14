var kind_map = {
    1: "command",
    2: "event",
    3: "message",
};

var kind_icon = {
    1: "⌘",
    2: "↯",
    3: "✉️",
}

var console_log = document.getElementById('console_log');
// var should_scroll = false;

frame_kind_to_html = function (frame) {
    var span = document.createElement('span');
    span.classList.add('frame-kind');
    span.classList.add('frame-kind-' + kind_map[frame.kind]);
    var text = document.createTextNode(kind_icon[frame.kind]);
    span.appendChild(text);
    span.appendChild(document.createTextNode(" "));
    return span;
};

frame_name_to_html = function (frame) {
    var span = document.createElement('span');
    span.classList.add('frame-name');
    span.classList.add('frame-kind-' + kind_map[frame.kind]);
    var text = document.createTextNode(frame.name);
    span.appendChild(text);
    span.appendChild(document.createTextNode(" "));
    return span;
}

frame_data_to_html = function (frame) {
    var span = document.createElement('span');
    span.classList.add('frame-data');
    if (!isEmpty(frame.data)) {
        var text = document.createTextNode(JSON.stringify(frame.data));
        span.appendChild(text);
    }
    span.appendChild(document.createTextNode(" "));
    return span;
}

frame_meta_to_html = function (frame) {
    var span = document.createElement('span');
    span.classList.add('frame-meta');
    if ('source' in frame.meta) {
        var subspan = document.createElement('span');
        var text = document.createTextNode(frame.meta.source.name);
        subspan.classList.add('frame-meta-source');
        subspan.appendChild(text);
        span.appendChild(subspan);
    };
    if ('space' in frame.meta) {
        var subspan = document.createElement('span');
        var text = document.createTextNode(' [' + frame.meta.space.name +']:');
        subspan.classList.add('frame-meta-space');
        subspan.appendChild(text);
        span.appendChild(subspan);
    };
    span.appendChild(document.createTextNode(" "));
    return span;
}

function isEmpty(obj) {
    return Object.keys(obj).length === 0;
}

frame_to_html = function (frame) {
    var li = document.createElement('li');
    li.appendChild(frame_kind_to_html(frame))
    if ('meta' in frame && !isEmpty(frame.meta)) {
        li.appendChild(frame_meta_to_html(frame))
    };
    li.appendChild(frame_name_to_html(frame))
    if ('data' in frame && !isEmpty(frame.data)) {
        li.appendChild(frame_data_to_html(frame))
    };
    return li
};


frame_from_json = function (frame_as_json) {
    return JSON.parse(frame_as_json);
};

frame_to_json = function (frame) {
    return JSON.stringify(frame);
};

append_to_log = function (frame) {
    var frame_as_html = frame_to_html(frame)
    last = console_log.appendChild(frame_as_html);
    // if (should_scroll) {
        // window.scrollTo(0, document.body.scrollHeight);
        last.scrollIntoView();
    // };
};

// window.onscroll = function(event) {
//     if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight) {
//         should_scroll = true;
//     }
//     else {
//         should_scroll = false;
//     };
// };

var ws = new WebSocket('ws://' + document.domain + ':' + location.port + '/');

ws.onopen = function (event) {
    // var frame = {"kind": 1, "name": "login", "data": {"token": agent_token} };
    // ws.send(frame_to_json(frame));
    var frame = {"kind": 1, "name": "join", "data": {"spaces": "*"} };
    ws.send(frame_to_json(frame));
};

ws.onmessage = function (event) {
    console.log(event.data)
    var frame = frame_from_json(event.data);
    append_to_log(frame);
};

var input = document.getElementById('console_input');
var button = document.getElementById('console_button');

button.onclick = function() {
    var content = document.getElementById('console_input').value;
    var space_select = document.getElementById('console_space');
    var space_name = space_select.options[space_select.selectedIndex].value;
    var ckind = document.getElementById('console_kind');
    var kind = Number(ckind.options[ckind.selectedIndex].value);
    var frame = {"kind": kind, "name": content, "meta": {"spaces": space_name}};
    // console.log(frame)
    ws.send(frame_to_json(frame));
    input.select();
};


input.addEventListener("keyup", function(event) {
    if (event.keyCode === 13) {
        event.preventDefault();
        button.click();
        }
    });
