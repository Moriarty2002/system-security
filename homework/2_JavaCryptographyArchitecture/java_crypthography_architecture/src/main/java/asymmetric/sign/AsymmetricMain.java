package asymmetric.sign;

import asymmetric.CertificateGenerator;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;

import java.security.Security;
import java.security.cert.X509Certificate;

public class AsymmetricMain {

    static void main(String[] args) {
        Security.addProvider(new BouncyCastleProvider());

        AsymmetricKeysCA asymmetricKeysCA = new AsymmetricKeysCA();
        AsymmetricKeysUser asymmetricKeysUser = new AsymmetricKeysUser();

        PKCS10CertificationRequest csr = asymmetricKeysUser.generateCSR();

        X509Certificate certificate = asymmetricKeysCA.signCertificate(csr);
        System.out.println("Certificate: " + certificate);

        System.out.println("-------------------------------------------------");

        System.out.println("User Certificate info");
        System.out.println("- subject info: " + certificate.getSubjectX500Principal());
        System.out.println("- issuer info: " + certificate.getIssuerX500Principal());

        System.out.println("-------------------------------------------------");

        X509Certificate caCertificate = asymmetricKeysCA.getCACert();
        System.out.println("CA Certificate: " + caCertificate);
        for (int i = 0; i < caCertificate.getKeyUsage().length; i++) {
            if (caCertificate.getKeyUsage()[i])
                System.out.println("Key usage: " + CertificateGenerator.usageNames[i]);
        }
        try {
            certificate.verify(caCertificate.getPublicKey());
            certificate.checkValidity();
            System.out.println("Certificate valid");
        } catch (Exception e) {
            System.out.println("Certificate invalid");
        }
    }

}
