/* Webschmiede Agency Auth – Session-Token statt Klartext-Passwort im Header */
(function (w) {
  var TOKEN_KEY = "ws_agency_token";
  var USER_KEY = "ws_agency_user";

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  }
  function setToken(t) {
    if (t) sessionStorage.setItem(TOKEN_KEY, t);
    else sessionStorage.removeItem(TOKEN_KEY);
  }
  function getUser() {
    try {
      return JSON.parse(sessionStorage.getItem(USER_KEY) || "null");
    } catch (e) {
      return null;
    }
  }
  function setUser(u) {
    if (u) sessionStorage.setItem(USER_KEY, JSON.stringify(u));
    else sessionStorage.removeItem(USER_KEY);
  }
  function clear() {
    setToken("");
    setUser(null);
  }
  function headers(extra) {
    var h = Object.assign({ "Content-Type": "application/json" }, extra || {});
    var t = getToken();
    if (t) h["X-Agency-Token"] = t;
    return h;
  }
  async function login(username, password, totp) {
    var r = await fetch("/api/agency/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username || "",
        password: password || "",
        totp: totp || "",
      }),
    });
    var d = {};
    try {
      d = await r.json();
    } catch (e) {}
    if (!r.ok || !d.success) {
      var err = new Error(d.error || "Anmeldung fehlgeschlagen");
      err.needs_totp = !!d.needs_totp;
      err.status = r.status;
      throw err;
    }
    setToken(d.token);
    setUser(d.user || null);
    return d;
  }
  async function logout() {
    try {
      await fetch("/api/agency/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: headers(),
      });
    } catch (e) {}
    clear();
  }
  async function forgot(usernameOrEmail) {
    var r = await fetch("/api/auth/forgot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: usernameOrEmail }),
    });
    var d = {};
    try {
      d = await r.json();
    } catch (e) {}
    if (!r.ok || d.success === false) {
      throw new Error(d.error || "Reset fehlgeschlagen");
    }
    return d;
  }
  async function reset(token, password) {
    var r = await fetch("/api/auth/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token, password: password }),
    });
    return r.json();
  }

  w.AgencyAuth = {
    TOKEN_KEY: TOKEN_KEY,
    getToken: getToken,
    setToken: setToken,
    getUser: getUser,
    clear: clear,
    headers: headers,
    hdr: headers,
    login: login,
    logout: logout,
    forgot: forgot,
    reset: reset,
  };
})(window);
