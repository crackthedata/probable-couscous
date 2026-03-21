// Set your Python tracking server URL here (e.g., your Raspberry Pi public IP or ngrok domain)
const TRACKING_SERVER_URL = "https://your-custom-domain.com";

function processTrackedDrafts() {
    var label = GmailApp.getUserLabelByName("TrackMe");

    // If the label doesn't exist, log an error and exit
    if (!label) {
        console.error("The label 'TrackMe' was not found. Please create it first.");
        return;
    }

    var drafts = GmailApp.getDrafts();

    for (var i = 0; i < drafts.length; i++) {
        var message = drafts[i].getMessage();
        var thread = message.getThread();

        // Only process if the draft thread is labeled "TrackMe"
        var threadLabels = thread.getLabels();
        var hasLabel = threadLabels.some(l => l.getName() === "TrackMe");

        if (hasLabel) {

            var body = message.getBody();
            // Generate a unique ID for this email
            var emailId = "id_" + new Date().getTime();
            
            var encSubj = encodeURIComponent(message.getSubject() || "No Subject");
            var encTo = encodeURIComponent(message.getTo() || "Unknown Recipient");

            var rawFrom = message.getFrom() || "";
            var accountMatch = rawFrom.match(/<([^>]+)>/);
            var account = accountMatch ? accountMatch[1] : rawFrom.trim();
            if (!account) account = "Unknown Account";

            var encAccount = encodeURIComponent(account);

            // 1. Inject Open Tracker (Python Server)
            var pixelUrl = TRACKING_SERVER_URL + '/open/' + emailId + '?subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount;
            var pixel = '<img src="' + pixelUrl + '" width="1" height="1" alt="" style="display:none;" />';

            // 2. Wrap Links for Click Tracking
            var trackedBody = body.replace(/href="([^"]*)"/gi, function (match, p1) {
                // Don't double-wrap or wrap internal protocol links (mailto:)
                if (p1.includes(TRACKING_SERVER_URL) || p1.startsWith("mailto:")) {
                    return match;
                }
                return 'href="' + TRACKING_SERVER_URL + '/click?id=' + emailId + '&subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount + '&url=' + encodeURIComponent(p1) + '"';
            });

            // 3. Send and Clean Up
            GmailApp.sendEmail(message.getTo(), message.getSubject(), "", {
                htmlBody: trackedBody + pixel,
                cc: message.getCc(),
                bcc: message.getBcc()
            });

            // Clean up the draft
            drafts[i].deleteDraft();
            console.log("Sent tracked email with ID: " + emailId + " to: " + message.getTo());
        }
    }
}
