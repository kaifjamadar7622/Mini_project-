$(document).ready(function () {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');

    // Access the user's camera
    const video = document.getElementById('video');

    // Access the user's camera
    navigator.mediaDevices.getUser Media({ video: true })
        .then(stream => {
            video.srcObject = stream;
        })
        .catch(err => {
            alert("Error accessing the camera: " + err);
        });
    // Register employee
    $("#registerForm").submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: "/register_employee",
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
            success: function (res) {
                alert(res.message);
            },
            error: function (xhr) {
                alert(xhr.responseJSON.error);
            }
        });
    });

    // Capture and login with face
    $("#loginBtn").click(function () {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(blob => {
            let formData = new FormData();
            formData.append("face_image", blob);
            $.ajax({
                url: "/login",
                type: "POST",
                data: formData,
                processData: false,
                contentType: false,
                success: function (res) {
                    window.location.href = res.redirect;
                },
                error: function (xhr) {
                    alert(xhr.responseJSON.error);
                }
            });
        });
    });

    // Function to capture fingerprint
    function captureFingerprint(callback) {
        const captureXML = `<?xml version='1.0'?><CaptureRequest ver='1.0' env='P' fCount='1' fType='0' iCount='1' pCount='0' format='0' pidVer='2.0' timeout='20000' posh='UNKNOWN' captureTime='0' type='FMR' />`;
        $.ajax({
            url: "http://127.0.0.1:11100/rd/capture",
            type: "CAPTURE",
            data: captureXML,
            contentType: "text/xml; charset=utf-8",
            success: function (data) {
                const pidDataXml = new XMLSerializer().serializeToString(data);
                callback(pidDataXml);
            },
            error: function () {
                alert("Fingerprint capture failed.");
            }
        });
    }

    // Register fingerprint
    $("#registerFingerprintBtn").click(function () {
        const name = prompt("Enter name:");
        if (!name) return;
        captureFingerprint(function (pidDataXml) {
            $.post("/register_fingerprint", { name: name, pidData: pidDataXml }, function (res) {
                alert(res.message);
            }).fail(xhr => {
                alert(xhr.responseJSON.error);
            });
        });
    });

    // Login with fingerprint
    $("#loginFingerprintBtn").click(function () {
        captureFingerprint(function (pidDataXml) {
            $.post("/login_fingerprint", { pidData: pidDataXml }, function (res) {
                window.location.href = res.redirect;
            }).fail(xhr => {
                alert(xhr.responseJSON.error);
            });
        });
    });

    // Check-in and Check-out
    $("#checkInBtn").click(() => {
        $.post("/check_in", res => alert(res.message)).fail(xhr => alert(xhr.responseJSON.error));
    });
    $("#checkOutBtn").click(() => {
        $.post("/check_out", res => alert(res.message)).fail(xhr => alert(xhr.responseJSON.error));
    });

    // Logout
    $("#logoutBtn").click(() => {
        $.post("/logout", res => window.location.href = res.redirect).fail(xhr => alert(xhr.responseJSON.error));
    });

    // Load attendance report
    if (window.location.pathname === "/report") {
        $.get("/get_attendance_report", function (data) {
            let table = "";
            data.forEach(d => {
                table += `<tr><td>${d.name}</td><td>${d.check_in_time}</td><td>${d.check_out_time}</td><td>${d.status}</td></tr>`;
            });
            $("#reportTable").html(table);
        });
    }
});